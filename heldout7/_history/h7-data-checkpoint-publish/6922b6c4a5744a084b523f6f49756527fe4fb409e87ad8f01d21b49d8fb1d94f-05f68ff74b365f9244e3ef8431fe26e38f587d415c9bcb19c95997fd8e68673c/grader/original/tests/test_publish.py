import json

from checkpoint.publish import main


def write(root, transactions=(), deliveries=(), minimum=0, upper=0):
    root.mkdir(parents=True, exist_ok=True)
    docs = {'snapshot': {'cut': {'s': 0}, 'customers': [{'tenant': 't', 'id': 'c', 'seats': 1, 'tier': 'basic', 'active': True}],
                         'aliases': [{'tenant': 't', 'alias': 'a', 'customer': 'c'}]},
            'request': {'upper': {'s': upper}, 'minimum': {'s': minimum}},
            'transactions': list(transactions), 'deliveries': list(deliveries)}
    for name, value in docs.items():
        (root / ('%s.json' % name)).write_text(json.dumps(value))
    return root


def txn(name, order, offset, delta, decision='commit'):
    return {'id': name, 'order': order, 'decision': decision, 'parts': [{'shard': 's', 'first': offset, 'last': offset}],
            'depends': [], 'operations': [{'kind': 'adjust', 'tenant': 't', 'alias': 'a', 'delta': delta}]}


def test_empty_export_publishes_base(tmp_path):
    target = tmp_path / 'out' / 'checkpoint.json'
    assert main(['--data', str(write(tmp_path / 'data')), '--output', str(target)]) == 0
    result = json.loads(target.read_text())
    assert result['cut'] == {'s': 0} and result['included'] == [] and result['customers'][0]['seats'] == 1


def test_single_commit_replayed(tmp_path):
    data = write(tmp_path / 'data', [txn('x', 1, 1, 4)], [{'shard': 's', 'offset': 1, 'transaction': 'x'}], upper=1)
    target = tmp_path / 'checkpoint.json'
    assert main(['--data', str(data), '--output', str(target)]) == 0
    result = json.loads(target.read_text())
    assert result['cut'] == {'s': 1} and result['applied'] == ['x'] and result['customers'][0]['seats'] == 5


def test_conflicting_delivery_keeps_existing(tmp_path):
    rows = [{'shard': 's', 'offset': 1, 'transaction': 'x'}, {'shard': 's', 'offset': 1, 'transaction': 'y'}]
    data = write(tmp_path / 'data', [txn('x', 1, 1, 1)], rows, upper=1)
    target = tmp_path / 'checkpoint.json'
    target.write_text('{"previous": true}')
    assert main(['--data', str(data), '--output', str(target)]) != 0
    assert json.loads(target.read_text()) == {'previous': True}
