"""Regression coverage: customer restore, partial delivery, rollback, replay binding, parents and restart."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

import recovery
from recovery.store import digest

ROOT = Path(__file__).resolve().parent.parent
HISTORY = json.loads((ROOT / 'data/history.json').read_text())


def ev(s, n, t, o, k, b, a):
    return dict(shard=s, lsn=n, txid=t, ordinal=o, key=k, before=b, after=a)


def seal(t, rows, outcome='commit', parents=()):
    rows = sorted(rows, key=lambda e: e['lsn'])
    return dict(txid=t, outcome=outcome, parents=list(parents),
                parts={s: dict(lsns=[e['lsn'] for e in rows if e['shard'] == s], sha256=digest([e for e in rows if e['shard'] == s]))
                       for s in sorted({e['shard'] for e in rows})})


def anchor():
    return {'frontier': {'a': 0, 'b': 0}, 'values': {'a': {'x': '0'}, 'b': {'y': '0'}}, 'applied': []}


def basic():
    t1 = [ev('a', 1, 't1', 0, 'x', '0', '1'), ev('b', 1, 't1', 1, 'y', '0', '1')]
    t2 = [ev('a', 2, 't2', 0, 'x', 'garbage', 'bad')]
    t3 = [ev('a', 3, 't3', 1, 'x', '1', '3'), ev('b', 2, 't3', 0, 'y', '1', '3')]
    return {'events': t1 + t2 + t3, 'decisions': [seal('t3', t3, parents=['t1']), seal('t2', t2, 'abort'), seal('t1', t1)]}


def loaded(tmp_path, batch=None):
    store = str(tmp_path / 'db'); recovery.initialize(store, anchor()); recovery.ingest(store, 'load', 0, batch or basic()); return store


def restore(store, history=HISTORY):
    recovery.initialize(store, history['snapshot'])
    for b in history['batches']:
        recovery.ingest(store, b['request_id'], b['expected_version'], {'events': b['events'], 'decisions': b['decisions']})
    r = history['restore']
    return recovery.advance(store, r['request_id'], r['expected_version'], r['target'])


def test_customer_history_restores(tmp_path):
    result = restore(str(tmp_path / 'db'))
    assert result['version'] == 4 and result['frontier'] == {'ledger': 47, 'orders': 16, 'stock': 11}
    assert result['order'] == ['k-refund', 'r-shipment', 'd-invoice', 'b-audit', 'p-close', 'h-supplier', 't-restock', 'a-cancelled']
    assert result['values'] == {'ledger': {'acct-17': '1150', 'audit-1': 'ok'}, 'orders': {'inv-77': 'issued', 'ord-881': 'closed', 'ord-990': 'open'},
                                'stock': {'sku-4': '20', 'sku-9': '24'}}
    assert result['processed']['k-refund'] == 'abort' and result['processed']['a-cancelled'] == 'abort'


def test_aborts_consume_coordinates_without_before_checks(tmp_path):
    result = recovery.advance(loaded(tmp_path), 'go', 1, {'a': 3, 'b': 2})
    assert result['order'] == ['t1', 't2', 't3'] and result['values'] == {'a': {'x': '3'}, 'b': {'y': '3'}}


def test_partial_delivery_then_late_evidence(tmp_path):
    batch = basic(); last = batch['events'].pop(); store = loaded(tmp_path, batch)
    with pytest.raises(ValueError):
        recovery.advance(store, 'go', 1, {'a': 3, 'b': 2})
    recovery.ingest(store, 'late', 1, {'events': [last], 'decisions': []})
    assert recovery.advance(store, 'go', 2, {'a': 3, 'b': 2})['values']['b']['y'] == '3'


def test_customer_decision_delivered_late(tmp_path):
    store = str(tmp_path / 'db'); history = copy.deepcopy(HISTORY); late = history['batches'].pop()
    recovery.initialize(store, history['snapshot'])
    for b in history['batches']:
        recovery.ingest(store, b['request_id'], b['expected_version'], {'events': b['events'], 'decisions': b['decisions']})
    with pytest.raises(ValueError):
        recovery.advance(store, 'early', 2, history['restore']['target'])
    recovery.ingest(store, late['request_id'], late['expected_version'], {'events': [], 'decisions': late['decisions']})
    assert recovery.advance(store, 'late', 3, history['restore']['target'])['version'] == 4


def test_unclosed_cut_rejected_without_changes(tmp_path):
    store = loaded(tmp_path); before = recovery.inspect(store)
    with pytest.raises(ValueError):
        recovery.advance(store, 'bad', 1, {'a': 3, 'b': 1})
    assert recovery.inspect(store) == before


def test_late_before_image_failure_rolls_back_everything(tmp_path):
    batch = basic(); t3 = [e for e in batch['events'] if e['txid'] == 't3']; t3[-1]['before'] = 'wrong'
    batch['decisions'][0] = seal('t3', t3, parents=['t1']); store = loaded(tmp_path, batch); before = recovery.inspect(store)
    with pytest.raises(ValueError):
        recovery.advance(store, 'go', 1, {'a': 3, 'b': 2})
    assert recovery.inspect(store) == before


@pytest.mark.parametrize('parent', ['missing', 't2'])
def test_missing_or_aborted_parent(tmp_path, parent):
    batch = basic(); batch['decisions'][0]['parents'] = [parent]
    with pytest.raises(ValueError):
        recovery.advance(loaded(tmp_path, batch), 'go', 1, {'a': 3, 'b': 2})


def test_conflicting_evidence_rejects_whole_batch(tmp_path):
    store = loaded(tmp_path); bad = dict(basic()['events'][0], after='different'); extra = ev('a', 4, 'late', 0, 'x', '3', '4')
    with pytest.raises(ValueError):
        recovery.ingest(store, 'bad', 1, {'events': [extra, bad], 'decisions': []})
    assert recovery.inspect(store)['version'] == 1
    recovery.ingest(store, 'ok', 1, {'events': [dict(extra, after='5')], 'decisions': []})


def test_replay_is_bound_to_payload(tmp_path):
    store = loaded(tmp_path); first = recovery.advance(store, 'go', 1, {'a': 3, 'b': 2})
    recovery.ingest(store, 'empty', 2, {'events': [], 'decisions': []})
    assert recovery.advance(store, 'go', 1, {'b': 2, 'a': 3}) == first
    with pytest.raises(ValueError):
        recovery.ingest(store, 'go', 1, {'events': [], 'decisions': []})
    with pytest.raises(ValueError):
        recovery.advance(store, 'go', 3, {'a': 3, 'b': 2})


def test_restart_replays_from_a_fresh_process(tmp_path):
    store = str(tmp_path / 'db'); first = restore(store)
    script = ("import json,sys,recovery; h=json.load(open(sys.argv[2])); r=h['restore']; "
              "print(json.dumps({'now': recovery.inspect(sys.argv[1]), 'again': recovery.advance(sys.argv[1], r['request_id'], r['expected_version'], r['target'])}))")
    child = subprocess.run([sys.executable, '-c', script, store, str(ROOT / 'data/history.json')], capture_output=True, text=True, cwd=ROOT, timeout=30)
    assert child.returncode == 0, child.stderr
    out = json.loads(child.stdout); assert out['again'] == first and out['now']['version'] == 4


def test_two_processes_one_winner(tmp_path):
    store = loaded(tmp_path); gate = tmp_path / 'gate'
    script = ("import json,sys,time,pathlib,recovery\nstore,ready,gate,rid=sys.argv[1:]\npathlib.Path(ready).touch()\n"
              "while not pathlib.Path(gate).exists(): time.sleep(.005)\n"
              "try: print(json.dumps(recovery.advance(store,rid,1,{'a':3,'b':2})['version']))\nexcept ValueError: print('null')\n")
    children = [subprocess.Popen([sys.executable, '-c', script, store, str(tmp_path / f'r{i}'), str(gate), f'p{i}'], cwd=ROOT,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(2)]
    while not all((tmp_path / f'r{i}').exists() for i in range(2)):
        pass
    gate.touch(); results = [json.loads(c.communicate(timeout=30)[0]) for c in children]
    assert sorted(results, key=str) == sorted([2, None], key=str) and recovery.inspect(store)['version'] == 2


def test_restore_command_is_rerunnable(tmp_path):
    output = tmp_path / 'checkpoint.json'
    command = [sys.executable, '-m', 'recovery', 'restore', '--history', 'data/history.json', '--store', str(tmp_path / 'db'), '--output', str(output)]
    for _ in range(2):
        assert subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60).returncode == 0
        assert json.loads(output.read_text())['checkpoint_id'] == 'marlow-quay-2026-11-02'
