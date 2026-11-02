import json

from reconcile.reservations import availability, replay
from reconcile.runner import main


def batch(requests, budgets=None, workers=None):
    return {'batch': 'T', 'customer': 'Example', 'as_of': 1, 'slots': [1, 2],
            'workers': workers or {'1': 4, '2': 4}, 'budgets': budgets or {'root': 10, 'leaf': 4},
            'credentials': [{'id': 'root', 'parent': None, 'scopes': ['run'], 'start': 0, 'end': 5, 'pool': 'root'},
                            {'id': 'leaf', 'parent': 'root', 'scopes': ['run'], 'start': 0, 'end': 5, 'pool': 'leaf'}],
            'requests': [{'id': q, 'scopes': ['run'], 'units': u, 'duration': 1, 'earliest': 1, 'latest': 3, 'leaves': ['leaf']}
                         for q, u in requests],
            'routes': [{'id': 'via-' + q, 'request': q, 'credentials': ['root', 'leaf']} for q, _ in requests]}


def write(root, batch_doc, attempts=(), receipts=()):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'batch.json').write_text(json.dumps(batch_doc))
    (root / 'ledger.json').write_text(json.dumps({'attempts': list(attempts), 'receipts': list(receipts)}))
    return root


HOLD = [{'id': 'a1', 'key': 'k1', 'at': 0, 'credentials': ['root', 'leaf'], 'units': 2, 'transport': 'response'}]


def test_single_call_schedule(tmp_path):
    data = write(tmp_path / 'data', batch([('q1', 2)]))
    target = tmp_path / 'out' / 'schedule.json'
    assert main(['--data', str(data), '--output', str(target)]) == 0
    assert json.loads(target.read_text())['calls'] == [{'request': 'q1', 'route': 'via-q1', 'start': 1, 'pools': ['leaf', 'root']}]


def test_held_reservation_until_expiry():
    receipts = [{'id': 'r1', 'kind': 'reserve', 'at': 0, 'reservation': 'h1', 'attempt': 'a1', 'expires': 2}]
    doc = batch([])
    state = replay(doc, {'attempts': HOLD, 'receipts': receipts})
    assert state['h1']['state'] == 'held'
    assert availability(doc, state)['leaf'] == {'1': 2, '2': 4}


def test_conflicting_replay_keeps_existing_schedule(tmp_path):
    receipts = [{'id': 'r1', 'kind': 'reserve', 'at': 0, 'reservation': 'h1', 'attempt': 'a1', 'expires': 2},
                {'id': 'r1', 'kind': 'reserve', 'at': 0, 'reservation': 'h1', 'attempt': 'a1', 'expires': 3}]
    data = write(tmp_path / 'data', batch([('q1', 1)]), HOLD, receipts)
    target = tmp_path / 'schedule.json'
    target.write_text('{"previous": true}')
    assert main(['--data', str(data), '--output', str(target)]) != 0
    assert json.loads(target.read_text()) == {'previous': True}
