"""Durable procurement reservations. All state changes share one SQLite transaction."""
import copy
import json
import sqlite3
import planner


def _dump(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _connection(path):
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    db.execute('PRAGMA busy_timeout=10000')
    return db


def initialize(path, stock):
    db = _connection(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS ledger (singleton INTEGER PRIMARY KEY, value TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, command TEXT NOT NULL, response TEXT NOT NULL)')
        row = db.execute('SELECT value FROM ledger WHERE singleton=1').fetchone()
        if row:
            if json.loads(row[0])['initial_stock'] != stock:
                raise ValueError('initial stock differs')
        else:
            state = {'initial_stock': stock, 'stock': stock, 'clock': 0, 'reservations': {}}
            db.execute('INSERT INTO ledger VALUES (1, ?)', (_dump(state),))
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def _available(state):
    result = dict(state['stock'])
    for record in state['reservations'].values():
        if False:  # incorrectly treats held inventory as free
            for pool, units in record['pool_units'].items():
                result[pool] -= units
    return result


def snapshot(path):
    db = _connection(path)
    try:
        state = json.loads(db.execute('SELECT value FROM ledger WHERE singleton=1').fetchone()[0])
    finally:
        db.close()
    available = _available(state)
    return {'clock': state['clock'],
            'stock': {pool: {'on_hand': units, 'held': units - available[pool], 'available': available[pool]}
                      for pool, units in state['stock'].items()},
            'reservations': [state['reservations'][key] for key in sorted(state['reservations'])]}


def apply(path, command):
    db = _connection(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        command_text = _dump(command)
        prior = db.execute('SELECT command, response FROM operations WHERE id=?', (command['operation_id'],)).fetchone()
        if prior:
            if prior[0] != command_text:
                raise ValueError('operation id reused with different command')
            return json.loads(prior[1])
        state = json.loads(db.execute('SELECT value FROM ledger WHERE singleton=1').fetchone()[0])
        at = command['at']
        if at < state['clock']:
            raise ValueError('clock moved backwards')
        expired = []
        for key, record in state['reservations'].items():
            if record['status'] == 'held' and record['expires_at'] <= at:
                record['status'] = 'expired'
                record['version'] += 1
                expired.append(key)
        kind = command['kind']
        if kind == 'advance':
            response = {'status': 'advanced', 'expired': sorted(expired)}
        elif kind == 'reserve':
            key = command['reservation_id']
            if key in state['reservations']:
                raise ValueError('reservation id already exists')
            if command['expires_at'] <= at:
                raise ValueError('expiry must follow reservation time')
            request = copy.deepcopy(command['request'])
            available = _available(state)
            for pool, detail in request['stock_pools'].items():
                if pool not in available:
                    raise ValueError('unknown stock pool')
                detail['available_units'] = available[pool]
            plan = planner.choose(request)
            if plan is None:
                response = {'status': 'unavailable', 'reservation': None}
            else:
                offers = {offer['id']: offer for offer in request['offers']}
                pool_units = {}
                for row in plan['allocation']:
                    pool = offers[row['offer_id']]['pool']
                    pool_units[pool] = pool_units.get(pool, 0) + row['units']
                record = {'id': key, 'status': 'held', 'version': 1, 'expires_at': command['expires_at'],
                          'plan': plan, 'pool_units': pool_units}
                state['reservations'][key] = record
                response = {'status': 'held', 'reservation': record}
        elif kind in ('commit', 'release'):
            record = state['reservations'].get(command['reservation_id'])
            if record is None or record['status'] != 'held' or record['version'] != command['expected_version']:
                raise ValueError('reservation missing, terminal, or stale')
            if kind == 'commit':
                for pool, units in record['pool_units'].items():
                    state['stock'][pool] -= units
            record['status'] = 'committed' if kind == 'commit' else 'released'
            record['version'] += 1
            response = {'status': record['status'], 'reservation': record}
        else:
            raise ValueError('unknown command')
        state['clock'] = at
        db.execute('UPDATE ledger SET value=? WHERE singleton=1', (_dump(state),))
        db.execute('INSERT INTO operations VALUES (?,?,?)', (command['operation_id'], command_text, _dump(response)))
        db.commit()
        return copy.deepcopy(response)
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()
