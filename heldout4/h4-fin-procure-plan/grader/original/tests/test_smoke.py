import reservations


def order():
    return {'demand': {'widget': 1}, 'deadline_days': 2,
            'suppliers': {'s': {'approved': True, 'shipping_cents': 3, 'min_units': 0, 'max_units': 5,
                                'capacity': {}, 'discounts': [{'minimum_units':0,'discount_bps':0}]}},
            'stock_pools': {'p': {'supplier':'s','sku':'widget','available_units':5}},
            'offers': [{'id':'o','supplier':'s','sku':'widget','pool':'p','stock':5,'pack_size':1,
                        'unit_cents':17,'lead_days':1,'resources_per_unit':{}}]}


def test_fresh_inventory(tmp_path):
    path = str(tmp_path/'inventory.db')
    assert reservations.initialize(path, {'p':5}) is None
    assert reservations.snapshot(path) == {'clock':0,'stock':{'p':{'on_hand':5,'held':0,'available':5}},'reservations':[]}


def test_hold_then_release(tmp_path):
    path = str(tmp_path/'inventory.db')
    reservations.initialize(path, {'p':5})
    held = reservations.apply(path, {'operation_id':'reserve-1','at':1,'kind':'reserve','reservation_id':'r','expires_at':10,'request':order()})
    assert held['status']=='held' and held['reservation']['plan']['cost_cents']==20
    assert reservations.snapshot(path)['stock']['p'] == {'on_hand':5,'held':1,'available':4}
    released = reservations.apply(path, {'operation_id':'release-1','at':2,'kind':'release','reservation_id':'r','expected_version':1})
    assert released['status']=='released' and released['reservation']['version']==2
    assert reservations.snapshot(path)['stock']['p'] == {'on_hand':5,'held':0,'available':5}
