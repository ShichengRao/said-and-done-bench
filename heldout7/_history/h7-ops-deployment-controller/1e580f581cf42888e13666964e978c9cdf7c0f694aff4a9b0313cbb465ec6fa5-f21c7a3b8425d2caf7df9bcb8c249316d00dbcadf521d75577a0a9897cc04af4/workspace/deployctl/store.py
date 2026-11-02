"""SQLite-backed controller state. Every read-modify-write runs in one BEGIN IMMEDIATE transaction."""
import copy
import json
import sqlite3
from contextlib import contextmanager


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


@contextmanager
def transaction(path):
    db = sqlite3.connect(path, timeout=30)
    try:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS control(id INTEGER PRIMARY KEY,value TEXT)')
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def load(db):
    row = db.execute('SELECT value FROM control WHERE id=1').fetchone()
    if row is None:
        raise ValueError('uninitialized')
    return json.loads(row[0])


def save(db, state):
    db.execute('INSERT OR REPLACE INTO control VALUES(1,?)', (canonical(state),))


def summary(state):
    keys = ('version', 'epoch', 'observed', 'pending', 'handoffs', 'done', 'quarantine', 'faults_left', 'rollouts')
    result = {key: copy.deepcopy(state[key]) for key in keys}
    result['complete'] = state['rollouts'] is not None and len(state['done']) == len(state['rollouts'])
    return result


def valid_inventory(configuration, observed):
    if set(observed) != set(configuration['nodes']):
        return False
    present = [v for v in observed.values() if v is not None]
    return len(present) <= configuration['capacity'] and len({v['service'] for v in present}) == len(present)


def initialize(path, configuration):
    with transaction(path) as db:
        row = db.execute('SELECT value FROM control WHERE id=1').fetchone()
        if row:
            state = json.loads(row[0])
            if state['configuration'] != configuration:
                raise ValueError('different configuration')
        else:
            if not valid_inventory(configuration, configuration['initial']):
                raise ValueError('invalid inventory')
            state = dict(configuration=copy.deepcopy(configuration), version=0, epoch=0,
                         observed=copy.deepcopy(configuration['initial']), pending={}, handoffs={}, done=[],
                         quarantine=[], faults_left=0, rollouts=None, locations={}, attempts={}, settled={}, requests={})
            save(db, state)
        return summary(state)


def inspect(path):
    with transaction(path) as db:
        return summary(load(db))
