"""Single-buyer prototype. Add durable reservation transaction semantics from SPEC.md."""
import copy
import json
import sqlite3
import planner


def initialize(path, stock):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY, value TEXT)')
        initial = {'clock': 0, 'stock': stock, 'reservations': {}}
        db.execute('INSERT OR IGNORE INTO inventory VALUES (1, ?)', (json.dumps(initial),))


def _read(path):
    with sqlite3.connect(path) as db:
        return json.loads(db.execute('SELECT value FROM inventory WHERE id=1').fetchone()[0])


def snapshot(path):
    state = _read(path)
    held = dict.fromkeys(state['stock'], 0)
    for record in state['reservations'].values():
        if record['status'] == 'held':
            for pool, units in record['pool_units'].items():
                held[pool] += units
    return {'clock': state['clock'], 'stock': {pool: {'on_hand': n, 'held': held[pool], 'available': n-held[pool]} for pool,n in state['stock'].items()},
            'reservations': [state['reservations'][key] for key in sorted(state['reservations'])]}


def apply(path, command):
    state = _read(path)
    kind = command['kind']
    if kind == 'reserve':
        plan = planner.choose(command['request'])
        if plan is None:
            response = {'status':'unavailable','reservation':None}
        else:
            offers = {o['id']:o for o in command['request']['offers']}
            pools = {}
            for row in plan['allocation']:
                pool = offers[row['offer_id']]['pool']
                pools[pool] = pools.get(pool,0)+row['units']
            record = {'id':command['reservation_id'], 'status':'held', 'version':1,
                      'expires_at':command['expires_at'], 'plan':plan, 'pool_units':pools}
            state['reservations'][record['id']] = record
            response = {'status':'held','reservation':record}
    elif kind in ('commit','release'):
        record = state['reservations'][command['reservation_id']]
        if kind == 'commit':
            for pool, units in record['pool_units'].items():
                state['stock'][pool] -= units
        record['status'] = 'committed' if kind == 'commit' else 'released'
        record['version'] += 1
        response = {'status':record['status'],'reservation':record}
    elif kind == 'advance':
        response = {'status':'advanced','expired':[]}
    else:
        raise ValueError('unknown kind')
    state['clock'] = command['at']
    with sqlite3.connect(path) as db:
        db.execute('UPDATE inventory SET value=? WHERE id=1', (json.dumps(state),))
    return copy.deepcopy(response)
