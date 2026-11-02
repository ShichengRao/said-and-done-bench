from procurement import service as p

CATALOG = {'warehouses': {'east': {'unit_fee': 0, 'activation_fee': 1}},
           'recipes': {'red': {'only': {'ingredients': {'red': 1}, 'cost': 2}}},
           'stock': [{'warehouse': 'east', 'ingredient': 'red', 'quantity': 1}]}


def test_empty_store(tmp_path):
    db = str(tmp_path / 'db'); cat = {'warehouses': {}, 'recipes': {}, 'stock': []}
    assert p.initialize(db, cat)['clock'] == 0
    assert p.apply(db, {'operation_id': 'tick', 'at': 1, 'kind': 'tick'})['result'] == 'ticked'


def test_reserve_commit_and_replay(tmp_path):
    db = str(tmp_path / 'db'); p.initialize(db, CATALOG)
    cmd = {'operation_id': 'r', 'at': 1, 'kind': 'reserve', 'basket': 'x', 'until': 5, 'request': {'needs': {'red': 1}, 'warehouses': ['east']}}
    out = p.apply(db, cmd)
    assert out['result'] == 'reserved' and out['baskets'][0]['cost'] == 3
    assert p.apply(db, cmd) == out
    assert p.apply(db, {'operation_id': 'c', 'at': 2, 'kind': 'commit', 'basket': 'x', 'expected_version': 1})['result'] == 'committed'
    assert p.snapshot(db)['stock'][0] == {'warehouse': 'east', 'ingredient': 'red', 'on_hand': 0, 'held': 0, 'available': 0}
