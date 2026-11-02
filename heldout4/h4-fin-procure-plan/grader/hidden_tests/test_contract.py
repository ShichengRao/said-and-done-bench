import copy
import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
import reservations as api


def request(units=1, *, pools=('p',), price=17, freight=3, exported=99):
    return {'demand': {pool: units for pool in pools}, 'deadline_days': 2,
            'suppliers': {'s': {'approved': True, 'shipping_cents': freight, 'min_units': 0, 'max_units': 12, 'capacity': {}, 'discounts': [{'minimum_units': 0, 'discount_bps': 0}]}},
            'stock_pools': {pool: {'supplier': 's', 'sku': pool, 'available_units': exported} for pool in pools},
            'offers': [{'id': pool, 'supplier': 's', 'sku': pool, 'pool': pool, 'stock': 5, 'pack_size': 1, 'unit_cents': price, 'lead_days': 1, 'resources_per_unit': {}} for pool in pools]}


def reserve(op='o', rid='r', at=1, expiry=10, req=None):
    return {'operation_id': op, 'kind': 'reserve', 'at': at, 'reservation_id': rid, 'expires_at': expiry, 'request': request() if req is None else req}


def action(kind, op, rid='r', at=2, version=1):
    return {'operation_id': op, 'kind': kind, 'at': at, 'reservation_id': rid, 'expected_version': version}


def advance(op='tick', at=10):
    return {'operation_id': op, 'kind': 'advance', 'at': at}


def store(tmp_path, stock=None, name='inventory.db'):
    path = str(tmp_path / name)
    assert api.initialize(path, {'p': 5} if stock is None else stock) is None
    return path


def assert_stock(path, pool, on_hand, held):
    assert api.snapshot(path)['stock'][pool] == {'on_hand': on_hand, 'held': held, 'available': on_hand-held}


def test_initialization_is_idempotent_not_reset_and_sqlite(tmp_path):
    path = store(tmp_path)
    assert api.snapshot(path) == {'clock': 0, 'stock': {'p': {'on_hand': 5, 'held': 0, 'available': 5}}, 'reservations': []}
    api.apply(path, reserve())
    before = api.snapshot(path)
    api.initialize(path, {'p': 5})
    assert api.snapshot(path) == before
    with pytest.raises(ValueError):
        api.initialize(path, {'p': 6})
    assert api.snapshot(path) == before
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
    empty = store(tmp_path, {}, 'empty.db')
    assert api.snapshot(empty) == {'clock': 0, 'stock': {}, 'reservations': []}


def test_exact_lifecycle_separates_hold_from_consumption(tmp_path):
    path = store(tmp_path, {'p': 4, 'q': 3})
    cmd = reserve(req=request(2, pools=('p','q')))
    original = copy.deepcopy(cmd)
    result = api.apply(path, cmd)
    expected = {'id': 'r', 'status': 'held', 'version': 1, 'expires_at': 10,
                'plan': {'cost_cents': 71, 'allocation': [{'offer_id': 'p', 'units': 2}, {'offer_id': 'q', 'units': 2}]},
                'pool_units': {'p': 2, 'q': 2}}
    assert result == {'status': 'held', 'reservation': expected}
    assert cmd == original
    assert_stock(path, 'p', 4, 2)
    assert_stock(path, 'q', 3, 2)
    committed = api.apply(path, action('commit', 'c'))
    assert committed == {'status': 'committed', 'reservation': dict(expected, status='committed', version=2)}
    assert_stock(path, 'p', 2, 0)
    assert_stock(path, 'q', 1, 0)
    before = api.snapshot(path)
    with pytest.raises(ValueError):
        api.apply(path, action('release', 'bad', version=2, at=3))
    assert api.snapshot(path) == before
    with pytest.raises(ValueError):
        api.apply(path, reserve('again', 'r', at=3))
    assert api.snapshot(path) == before


def test_release_frees_without_consuming_and_returns_detached_data(tmp_path):
    path = store(tmp_path)
    held = api.apply(path, reserve())
    held['reservation']['pool_units']['p'] = 999
    held['reservation']['plan']['cost_cents'] = -1
    snap = api.snapshot(path)
    snap['stock']['p']['on_hand'] = 0
    snap['reservations'][0]['status'] = 'committed'
    released = api.apply(path, action('release', 'release'))
    assert released['reservation']['version'] == 2
    assert released['reservation']['pool_units'] == {'p': 1}
    assert released['reservation']['plan']['cost_cents'] == 20
    assert released['status'] == 'released'
    assert_stock(path, 'p', 5, 0)


def test_stale_export_is_replaced_and_active_holds_reduce_stock(tmp_path):
    path = store(tmp_path, {'p': 3})
    first = api.apply(path, reserve(req=request(2, exported=0)))
    assert first['status'] == 'held'
    assert api.apply(path, reserve('second', 's', req=request(2))) == {'status': 'unavailable', 'reservation': None}
    assert_stock(path, 'p', 3, 2)
    third = api.apply(path, reserve('third', 't', req=request(1)))
    assert third['status'] == 'held'
    assert_stock(path, 'p', 3, 3)


def test_unavailable_is_atomic_durable_replay_and_name_not_consumed(tmp_path):
    path = store(tmp_path, {'p': 2, 'q': 0})
    cmd = reserve('unavailable', 'free', req=request(1, pools=('p','q')))
    assert api.apply(path, cmd) == {'status': 'unavailable', 'reservation': None}
    assert api.snapshot(path) == {'clock': 1, 'stock': {'p': {'on_hand': 2, 'held': 0, 'available': 2}, 'q': {'on_hand': 0, 'held': 0, 'available': 0}}, 'reservations': []}
    assert api.apply(path, reserve('new', 'free', at=2))['status'] == 'held'
    before = api.snapshot(path)
    assert api.apply(path, cmd) == {'status': 'unavailable', 'reservation': None}
    assert api.snapshot(path) == before
    with pytest.raises(ValueError):
        api.apply(path, dict(cmd, request=request()))
    assert api.snapshot(path) == before


def test_replay_precedes_clock_expiry_and_preserves_original_response(tmp_path):
    path = store(tmp_path)
    cmd = reserve()
    original = api.apply(path, cmd)
    api.apply(path, action('commit', 'commit'))
    api.apply(path, advance(at=50))
    before = api.snapshot(path)
    reordered = {key: cmd[key] for key in reversed(list(cmd))}
    reordered['request'] = {key: cmd['request'][key] for key in reversed(list(cmd['request']))}
    assert api.apply(path, reordered) == original
    assert api.snapshot(path) == before
    for changed in [dict(cmd, at=2), dict(cmd, expires_at=20), dict(cmd, reservation_id='different')]:
        with pytest.raises(ValueError):
            api.apply(path, changed)
        assert api.snapshot(path) == before
    with pytest.raises(ValueError):
        api.apply(path, advance('old', at=49))
    assert api.snapshot(path) == before


def test_expiry_is_inclusive_sorted_once_and_snapshot_readonly(tmp_path):
    path = store(tmp_path)
    api.apply(path, reserve('z', 'z', expiry=5))
    api.apply(path, reserve('a', 'a', expiry=5))
    api.apply(path, reserve('b', 'b', expiry=6))
    assert_stock(path, 'p', 5, 3)
    assert api.apply(path, advance('early', 4)) == {'status': 'advanced', 'expired': []}
    result = api.apply(path, advance('boundary', 5))
    assert result == {'status': 'advanced', 'expired': ['a','z']}
    assert_stock(path, 'p', 5, 1)
    assert [(r['id'], r['status'], r['version']) for r in api.snapshot(path)['reservations']] == [('a','expired',2),('b','held',1),('z','expired',2)]
    assert api.apply(path, advance('same', 5)) == {'status': 'advanced', 'expired': []}
    api.apply(path, advance('later', 6))
    before = api.snapshot(path)
    assert api.apply(path, advance('boundary', 5)) == result
    assert api.snapshot(path) == before


def test_error_rolls_back_tentative_expiry_clock_and_operation_id(tmp_path):
    path = store(tmp_path)
    api.apply(path, reserve(expiry=5))
    before = api.snapshot(path)
    rejected = action('commit', 'reusable', at=5)
    with pytest.raises(ValueError):
        api.apply(path, rejected)
    assert api.snapshot(path) == before
    corrected = action('commit', 'reusable', at=4)
    assert api.apply(path, corrected)['status'] == 'committed'
    assert_stock(path, 'p', 4, 0)
    # Unknown-pool validation also cannot persist another reservation's tentative expiry.
    api.apply(path, reserve('hold2', 'r2', at=4, expiry=6))
    before = api.snapshot(path)
    with pytest.raises(ValueError):
        api.apply(path, reserve('unknown', 'r3', at=6, req=request(pools=('missing',))))
    assert api.snapshot(path) == before
    assert api.apply(path, advance('unknown', 6)) == {'status': 'advanced', 'expired': ['r2']}


def test_expected_version_and_terminal_checks_are_atomic(tmp_path):
    path = store(tmp_path)
    api.apply(path, reserve())
    before = api.snapshot(path)
    for cmd in [action('commit','v',version=2), action('release','x',rid='missing')]:
        with pytest.raises(ValueError):
            api.apply(path,cmd)
        assert api.snapshot(path) == before
    assert api.apply(path, action('release','v'))['status'] == 'released'
    before = api.snapshot(path)
    with pytest.raises(ValueError):
        api.apply(path,action('commit','terminal',version=2))
    assert api.snapshot(path) == before


def child(path, command):
    script = 'import json,sys,reservations; p,c=json.loads(sys.stdin.read()); print(json.dumps(reservations.apply(p,c)))'
    p = subprocess.run([sys.executable, '-c', script], input=json.dumps([path, command]), text=True, capture_output=True, timeout=20)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def test_restart_persists_state_idempotency_and_initial_seed(tmp_path):
    path = store(tmp_path)
    cmd = reserve()
    first = child(path, cmd)
    assert_stock(path, 'p', 5, 1)
    api.initialize(path, {'p': 5})
    committed = child(path, action('commit', 'commit'))
    assert committed['status'] == 'committed'
    assert child(path, cmd) == first
    assert_stock(path, 'p', 4, 0)
    other = store(tmp_path, {'p': 2}, 'other.db')
    assert child(other, cmd)['status'] == 'held'
    assert_stock(other, 'p', 2, 1)
    assert_stock(path, 'p', 4, 0)


def race(path, commands):
    gate = Barrier(len(commands))
    def worker(command):
        gate.wait(timeout=5)
        try:
            return api.apply(path, command)
        except ValueError:
            return 'rejected'
    with ThreadPoolExecutor(max_workers=len(commands)) as pool:
        return list(pool.map(worker, commands))


def test_concurrent_buyers_cannot_oversell_shared_pool(tmp_path):
    path = store(tmp_path, {'p': 3})
    commands = [reserve(str(i), str(i)) for i in range(6)]
    responses = race(path, commands)
    assert sorted(x['status'] for x in responses) == ['held']*3 + ['unavailable']*3
    assert_stock(path, 'p', 3, 3)
    assert len(api.snapshot(path)['reservations']) == 3


def test_concurrent_identical_retry_and_conflicting_identity(tmp_path):
    path = store(tmp_path)
    responses = race(path, [reserve() for _ in range(6)])
    assert all(x == responses[0] for x in responses)
    assert_stock(path, 'p', 5, 1)
    competing = race(path, [reserve('same','a'), reserve('same','b')])
    assert competing.count('rejected') == 1
    assert sum(isinstance(x,dict) and x['status']=='held' for x in competing) == 1
    assert_stock(path, 'p', 5, 2)


def test_concurrent_commit_release_has_one_atomic_winner(tmp_path):
    path = store(tmp_path)
    api.apply(path,reserve())
    responses = race(path, [action('commit','c'), action('release','r')])
    assert responses.count('rejected') == 1
    winner = next(x for x in responses if x != 'rejected')
    assert winner['status'] in ('committed','released')
    assert winner['reservation']['version'] == 2
    assert_stock(path, 'p', 4 if winner['status']=='committed' else 5, 0)
    winner_cmd = action('commit','c') if winner['status']=='committed' else action('release','r')
    assert api.apply(path,winner_cmd) == winner


def test_competing_processes_share_inventory(tmp_path):
    path = store(tmp_path, {'p': 2})
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda i: child(path,reserve(str(i),str(i))), range(4)))
    assert sorted(x['status'] for x in results) == ['held','held','unavailable','unavailable']
    assert_stock(path, 'p', 2, 2)


def test_supplied_planner_zero_price_still_pays_freight_and_pool_aggregation(tmp_path):
    path = store(tmp_path, {'p': 3})
    req = request(2, price=0, freight=27)
    req['offers'][0]['stock'] = 1
    second = dict(req['offers'][0], id='p2')
    req['offers'].append(second)
    result = api.apply(path,reserve(req=req))
    assert result['reservation']['plan'] == {'cost_cents': 27, 'allocation': [{'offer_id':'p','units':1},{'offer_id':'p2','units':1}]}
    assert result['reservation']['pool_units'] == {'p':2}
    assert_stock(path,'p',3,2)


def test_unavailable_accepts_expiry_and_reserve_reuses_freed_pool(tmp_path):
    path = store(tmp_path, {'p':1,'q':0})
    api.apply(path,reserve(expiry=2))
    assert api.apply(path,reserve('none','n',at=2,req=request(pools=('p','q')))) == {'status':'unavailable','reservation':None}
    snap = api.snapshot(path)
    assert snap['clock']==2 and snap['reservations'][0]['status']=='expired'
    assert_stock(path,'p',1,0)
    assert api.apply(path,reserve('new','n',at=2))['status']=='held'


def test_generated_lifecycles_with_independent_stock_accounting(tmp_path):
    import random
    rng = random.Random(41827)
    for scenario in range(10):
        pool = 'lot-' + str(rng.randrange(1000,9999))
        on_hand = rng.randrange(1,6)
        path = store(tmp_path, {pool:on_hand}, 'generated-'+str(scenario)+'.db')
        expected_records = []
        for cycle in range(4):
            at = cycle*3+1
            units = rng.randrange(1,6)
            rid = 'reservation-'+str(cycle)
            cmd = reserve('reserve-'+str(cycle),rid,at=at,expiry=at+2,req=request(units,pools=(pool,)))
            response = api.apply(path,cmd)
            if units > on_hand:
                assert response == {'status':'unavailable','reservation':None}
                assert api.apply(path,advance('advance-'+str(cycle),at+2)) == {'status':'advanced','expired':[]}
            else:
                expected = {'id':rid,'status':'held','version':1,'expires_at':at+2,
                            'plan':{'cost_cents':units*17+3,'allocation':[{'offer_id':pool,'units':units}]},
                            'pool_units':{pool:units}}
                assert response == {'status':'held','reservation':expected}
                assert_stock(path,pool,on_hand,units)
                mode = rng.choice(['commit','release','expire'])
                if mode == 'expire':
                    assert api.apply(path,advance('advance-'+str(cycle),at+2)) == {'status':'advanced','expired':[rid]}
                    expected = dict(expected,status='expired',version=2)
                else:
                    terminal = 'committed' if mode=='commit' else 'released'
                    expected = dict(expected,status=terminal,version=2)
                    assert api.apply(path,action(mode,'finish-'+str(cycle),rid,at=at+1)) == {'status':terminal,'reservation':expected}
                    if mode=='commit':
                        on_hand -= units
                expected_records.append(expected)
            before = api.snapshot(path)
            assert api.apply(path,cmd) == response
            assert api.snapshot(path) == before
            assert_stock(path,pool,on_hand,0)
            assert api.snapshot(path)['reservations'] == expected_records


def test_live_hold_changes_coupled_planner_result_and_list_order_is_identity(tmp_path):
    path = store(tmp_path, {'ax':2,'ay':1,'bx':2})
    def supplier(freight, discounts):
        return {'approved':True,'shipping_cents':freight,'min_units':0,'max_units':5,
                'capacity':{'dispatch':3},'discounts':discounts}
    def offer(oid, supplier_id, sku, stock, pack, price):
        return {'id':oid,'supplier':supplier_id,'sku':sku,'pool':oid,'stock':stock,'pack_size':pack,
                'unit_cents':price,'lead_days':1,'resources_per_unit':{'dispatch':1}}
    req = {'demand':{'x':2,'y':1},'deadline_days':2,
           'suppliers':{'a':supplier(4,[{'minimum_units':3,'discount_bps':1000},{'minimum_units':0,'discount_bps':0}]),
                        'b':supplier(0,[{'minimum_units':0,'discount_bps':0}])},
           'stock_pools':{'ax':{'supplier':'a','sku':'x','available_units':99},
                          'ay':{'supplier':'a','sku':'y','available_units':99},
                          'bx':{'supplier':'b','sku':'x','available_units':99}},
           'offers':[offer('bx','b','x',2,1,8),offer('ax','a','x',2,2,5),offer('ay','a','y',1,1,8)]}
    subset = copy.deepcopy(req)
    subset['demand'] = {'x':2}
    subset['stock_pools'].pop('ay')
    subset['offers'] = [row for row in subset['offers'] if row['sku']=='x']
    first = api.apply(path,reserve('first','first',req=subset))
    assert first['reservation']['plan'] == {'cost_cents':14,'allocation':[{'offer_id':'ax','units':2}]}
    cmd = reserve('second','second',req=req)
    before_cmd = copy.deepcopy(cmd)
    second = api.apply(path,cmd)
    assert second['reservation']['plan'] == {'cost_cents':28,'allocation':[{'offer_id':'ay','units':1},{'offer_id':'bx','units':2}]}
    assert second['reservation']['pool_units'] == {'ay':1,'bx':2}
    assert cmd == before_cmd
    before = api.snapshot(path)
    changed = copy.deepcopy(cmd)
    changed['request']['offers'].reverse()
    with pytest.raises(ValueError):
        api.apply(path,changed)
    assert api.snapshot(path) == before
    api.apply(path,action('release','release-first','first'))
    assert_stock(path,'ax',2,0)
    assert_stock(path,'ay',1,1)
    assert_stock(path,'bx',2,2)
    # A fresh store independently exercises the volume-discount choice without the hold.
    clean = store(tmp_path,{'ax':2,'ay':1,'bx':2},'clean.db')
    result = api.apply(clean,reserve(req=req))
    assert result['reservation']['plan'] == {'cost_cents':20,'allocation':[{'offer_id':'ax','units':2},{'offer_id':'ay','units':1}]}
