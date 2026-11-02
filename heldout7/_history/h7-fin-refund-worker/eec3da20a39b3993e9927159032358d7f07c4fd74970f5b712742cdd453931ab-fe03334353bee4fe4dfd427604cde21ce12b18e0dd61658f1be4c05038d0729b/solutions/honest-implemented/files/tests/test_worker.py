import json
import subprocess
import sys
from pathlib import Path

from refund_worker import cli, service as r

ROOT = Path(__file__).resolve().parent.parent


def captures():
    return [dict(id='c1', merchant='m', currency='USD', captured_cents=100, refund_until=20),
            dict(id='c2', merchant='m', currency='USD', captured_cents=80, refund_until=30)]


def setup(tmp_path, cents=70):
    db = str(tmp_path / 'db'); r.initialize(db, captures())
    r.apply(db, dict(operation_id='reserve', at=1, kind='reserve', refund='r', merchant='m', currency='USD', cents=cents, until=15, candidates=['c1', 'c2']))
    return db


def version(db):
    return next(x['version'] for x in r.snapshot(db)['refunds'] if x['id'] == 'r')


def command(db, op, kind, at=1, **kw):
    return r.apply(db, dict(operation_id=op, kind=kind, at=at, **kw))


def dispatch(db, op='dispatch', at=1, until=5, kind='refund'):
    return command(db, op, 'dispatch', at, refund='r', expected_version=version(db), provider_kind=kind, worker='worker', until=until)


def receipt(db, op, result, at=2, kind='refund', receipt_id=None):
    return command(db, op, 'receipt', at, receipt_id=receipt_id or op, provider_operation=kind + '/r', result=result)


def balances(db):
    return {c['id']: (c['held_cents'], c['refunded_cents'], c['available_cents']) for c in r.snapshot(db)['captures']}


def test_cancel_inflight_keeps_exposure_and_late_success_compensates(tmp_path):
    db = setup(tmp_path); dispatch(db)
    assert command(db, 'cancel', 'cancel', 2, refund='r', expected_version=version(db))['refund']['status'] == 'cancel_pending'
    assert balances(db)['c1'] == (70, 0, 30)
    command(db, 'later', 'tick', 6)
    assert receipt(db, 'late', 'succeeded', 6)['refund']['status'] == 'compensating'  # lease expired, truth still applies
    dispatch(db, 'comp', 7, 10, 'compensation'); assert balances(db)['c1'] == (0, 70, 30)
    command(db, 'abandon', 'abandon', 8, provider_operation='compensation/r', lease_token='compensation/r/1')
    out = dispatch(db, 'comp-2', 9, 10, 'compensation')
    assert out['provider_operation']['id'] == 'compensation/r' and out['provider_operation']['lease']['token'] == 'compensation/r/2'
    assert receipt(db, 'comp-ok', 'succeeded', 11, 'compensation')['refund']['status'] == 'compensated'
    assert balances(db)['c1'] == (0, 0, 100)


def test_stale_lease_cannot_abandon_new_worker(tmp_path):
    db = setup(tmp_path); dispatch(db); dispatch(db, 'retry', 5, 8); before = r.snapshot(db)
    try:
        command(db, 'old', 'abandon', 5, provider_operation='refund/r', lease_token='refund/r/1'); raise AssertionError
    except ValueError:
        pass
    assert r.snapshot(db) == before


def test_duplicate_and_conflicting_receipts(tmp_path):
    db = setup(tmp_path); dispatch(db); receipt(db, 'ok', 'succeeded')
    assert receipt(db, 'again', 'succeeded', receipt_id='ok')['result'] == 'receipt_replayed'
    assert receipt(db, 'old', 'accepted')['result'] == 'receipt_ignored'
    before = r.snapshot(db)
    for args in [('conflict', 'failed'), ('reuse', 'accepted', 2, 'refund', 'ok')]:
        try:
            receipt(db, *args); raise AssertionError
        except ValueError:
            pass
    assert r.snapshot(db) == before


def test_compensation_failure_and_dispatch_do_not_restore(tmp_path):
    db = setup(tmp_path, 130); dispatch(db)
    command(db, 'cancel', 'cancel', 2, refund='r', expected_version=version(db)); receipt(db, 'ok', 'succeeded')
    dispatch(db, 'comp', 2, 5, 'compensation'); assert balances(db) == {'c1': (0, 100, 0), 'c2': (0, 30, 50)}
    assert receipt(db, 'bad', 'failed', 3, 'compensation')['refund']['status'] == 'compensation_failed'
    assert balances(db) == {'c1': (0, 100, 0), 'c2': (0, 30, 50)}


def test_replay_before_clock_and_from_fresh_process(tmp_path):
    db = setup(tmp_path); send = dict(operation_id='send', at=1, kind='dispatch', refund='r', expected_version=1, provider_kind='refund', worker='w', until=5)
    first = r.apply(db, send); command(db, 'tick', 'tick', 6)
    assert r.apply(db, send) == first
    child = subprocess.run([sys.executable, '-c', 'import json,sys;from refund_worker import service as r;print(json.dumps(r.apply(sys.argv[1],json.loads(sys.argv[2]))))', db, json.dumps(send)],
                           cwd=ROOT, capture_output=True, text=True, check=True)
    assert json.loads(child.stdout) == first


def test_customer_history_reconciles_and_reruns(tmp_path):
    history = json.loads((ROOT / 'data/provider_history.json').read_text())
    first = cli.run_history(history, tmp_path / 'store.db'); again = cli.run_history(history, tmp_path / 'store.db')
    assert first == again
    assert [x['result'] for x in first['responses']][-1] == 'received'
    assert {x['id']: x['status'] for x in first['state']['refunds']} == {'r': 'compensated', 'waiting': 'expired'}
    assert all(c['held_cents'] == c['refunded_cents'] == 0 for c in first['state']['captures'])
