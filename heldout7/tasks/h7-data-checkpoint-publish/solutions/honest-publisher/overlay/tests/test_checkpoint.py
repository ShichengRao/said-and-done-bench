import copy
import json
from pathlib import Path

from checkpoint.cut import consistent_cut
from checkpoint.evidence import load
from checkpoint.publish import BelowMinimum, build, main

DATA = Path(__file__).resolve().parent.parent / 'data'


def part(shard, offset):
    return {'shard': shard, 'first': offset, 'last': offset}


def test_customer_export_checkpoint():
    result = build(load(DATA))
    assert result['cut'] == {'archive': 2, 'crm': 2, 'tickets': 2}
    assert result['included'] == ['m41', 'm58', 'm63'] and result['applied'] == ['m41', 'm58']
    assert result['deferred'] == ['m77', 'm82', 'm96']
    assert [(c['tenant'], c['id'], c['seats'], c['tier']) for c in result['customers']] == [
        ('cedar', 'c1', 13, 'plus'), ('cedar', 'c2', 4, 'plus'), ('larch', 'c1', 2, 'basic')]
    assert {'tenant': 'cedar', 'alias': 'team', 'customer': 'c2'} in result['aliases']


def test_dependency_on_unresolved_pulls_other_shard_back():
    table = {'p': {'id': 'p', 'order': 1, 'decision': 'unresolved', 'parts': [part('a', 1)], 'depends': []},
             'd': {'id': 'd', 'order': 2, 'decision': 'commit', 'parts': [part('b', 1)], 'depends': ['p']}}
    assert consistent_cut(table, {'a': 1, 'b': 1}) == {'a': 0, 'b': 0}


def test_partial_transaction_cascades():
    table = {'x': {'id': 'x', 'order': 1, 'decision': 'commit', 'parts': [part('a', 2), part('b', 1)], 'depends': []},
             'y': {'id': 'y', 'order': 2, 'decision': 'commit', 'parts': [part('b', 2), part('c', 1)], 'depends': []}}
    assert consistent_cut(table, {'a': 1, 'b': 2, 'c': 1}) == {'a': 1, 'b': 0, 'c': 0}


def test_out_of_order_and_replayed_deliveries():
    export = load(DATA)
    shuffled = copy.deepcopy(export)
    shuffled['deliveries'] = list(reversed(shuffled['deliveries'])) + shuffled['deliveries'][:2]
    shuffled['transactions'].reverse()
    assert build(shuffled) == build(export)


def test_abort_applies_nothing_but_satisfies_dependency():
    export = load(DATA)
    for txn in export['transactions']:
        if txn['id'] == 'm77':
            txn['decision'] = 'abort'
    result = build(export)
    assert result['cut'] == {'archive': 4, 'crm': 4, 'tickets': 4} and 'm77' not in result['applied']
    assert 'm82' in result['applied'] and 'm96' in result['applied']


def test_minimum_not_reached_keeps_existing(tmp_path):
    export = load(DATA)
    export['request']['minimum'] = dict(export['request']['upper'])
    try:
        build(export)
    except BelowMinimum:
        pass
    else:
        raise AssertionError('expected BelowMinimum')
    data = tmp_path / 'data'; data.mkdir()
    for name, value in export.items():
        (data / ('%s.json' % name)).write_text(json.dumps(value))
    target = tmp_path / 'checkpoint.json'; target.write_text('{"previous": true}')
    assert main(['--data', str(data), '--output', str(target)]) != 0
    assert json.loads(target.read_text()) == {'previous': True}
