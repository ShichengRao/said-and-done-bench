import copy
import json
import subprocess
import sys
from pathlib import Path
import pytest
from procurement import service as p

ROOT = Path(__file__).resolve().parent.parent


def catalog():
    return json.loads((ROOT / 'data/customer_update.json').read_text())['catalog']


def reserve(db, op, basket, product, warehouses, at=1, until=100):
    return p.apply(db, dict(operation_id=op, at=at, kind='reserve', basket=basket, until=until, request=dict(needs={product: 1}, warehouses=warehouses)))


def setup(tmp_path):
    db = str(tmp_path / 'db'); p.initialize(db, catalog())
    reserve(db, 'hold-red', 'third-red', 'red', ['east']); reserve(db, 'hold-blue', 'third-blue', 'blue', ['west'])
    reserve(db, 'old-a', 'a', 'alpha', ['west']); reserve(db, 'old-b', 'b', 'beta', ['east'])
    return db


def joint(op='joint', at=2):
    return dict(operation_id=op, at=at, kind='exchange', entries=[
        dict(basket='a', expected_version=1, until=200, request=dict(needs={'beta': 1}, warehouses=['east'])),
        dict(basket='b', expected_version=1, until=200, request=dict(needs={'alpha': 1}, warehouses=['west']))])


def test_shared_stock_joint_exchange_credits_both_old_holds(tmp_path):
    db = setup(tmp_path); before = p.snapshot(db)
    single = dict(joint('alone'), entries=joint()['entries'][:1])
    assert p.apply(db, single)['result'] == 'unavailable'
    out = p.apply(db, joint())
    assert out['result'] == 'exchanged' and [b['version'] for b in out['baskets']] == [2, 2]
    assert [b for b in p.snapshot(db)['baskets'] if b['id'].startswith('third')] == [b for b in before['baskets'] if b['id'].startswith('third')]
    assert all(r['available'] == 0 for r in p.snapshot(db)['stock'])


def test_unavailable_exchange_keeps_old_holds_and_rollback_on_error(tmp_path):
    db = setup(tmp_path); before = p.snapshot(db)
    bad = joint('stale'); bad['entries'][0]['expected_version'] = 2
    with pytest.raises(ValueError):
        p.apply(db, bad)
    assert p.snapshot(db) == before
    huge = dict(joint('huge'), entries=[dict(joint()['entries'][0], request=dict(needs={'alpha': 3}, warehouses=['east', 'west']))])
    assert p.apply(db, huge)['baskets'] == [b for b in before['baskets'] if b['id'] == 'a']


def test_retry_replays_original_response_without_rebooking(tmp_path):
    db = setup(tmp_path); first = p.apply(db, joint()); frozen = copy.deepcopy(first)
    first['baskets'][0]['units'].clear(); p.apply(db, dict(operation_id='later', at=4, kind='tick'))
    assert p.apply(db, joint()) == frozen
    with pytest.raises(ValueError):
        p.apply(db, joint(at=4))


def test_locally_cheapest_choice_is_not_used(tmp_path):
    cat = catalog(); cat['warehouses'] = {'west': dict(unit_fee=0, activation_fee=0)}
    cat['stock'] = [dict(warehouse='west', ingredient='red', quantity=2), dict(warehouse='west', ingredient='blue', quantity=1)]
    db = str(tmp_path / 'db'); p.initialize(db, cat)
    out = p.apply(db, dict(operation_id='r', at=1, kind='reserve', basket='x', until=10, request=dict(needs={'alpha': 1, 'red': 1}, warehouses=['west'])))
    assert out['result'] == 'reserved' and out['baskets'][0]['units'][0]['recipe'] == 'b'


def test_customer_update_cli_is_idempotent(tmp_path):
    args = [sys.executable, '-m', 'procurement', 'apply', '--input', str(ROOT / 'data/customer_update.json'),
            '--store', str(tmp_path / 's.db'), '--output', str(tmp_path / 'out.json')]
    assert subprocess.run(args, cwd=ROOT, capture_output=True).returncode == 0
    first = json.loads((tmp_path / 'out.json').read_text())
    assert subprocess.run(args, cwd=ROOT, capture_output=True).returncode == 0
    assert json.loads((tmp_path / 'out.json').read_text()) == first and first['responses'][-1]['result'] == 'exchanged'
