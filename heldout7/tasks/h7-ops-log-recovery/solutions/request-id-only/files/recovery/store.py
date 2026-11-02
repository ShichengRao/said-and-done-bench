"""SQLite-backed recovery state: frontier, values, processed decisions, buffered evidence and request log."""
import copy
import hashlib
import json
import sqlite3
from contextlib import contextmanager


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@contextmanager
def transaction(path):
    """BEGIN IMMEDIATE takes the write lock up front so competing processes serialize instead of failing."""
    db = sqlite3.connect(path, timeout=30)
    try:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS recovery(id INTEGER PRIMARY KEY, value TEXT NOT NULL)')
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def load(db):
    row = db.execute('SELECT value FROM recovery WHERE id=1').fetchone()
    if row is None:
        raise ValueError('recovery store is not initialized')
    return json.loads(row[0])


def save(db, state):
    db.execute('INSERT OR REPLACE INTO recovery VALUES(1, ?)', (canonical(state),))


def summary(state):
    return {key: copy.deepcopy(state[key]) for key in ('version', 'frontier', 'values', 'processed')}


def initialize(path, snapshot):
    with transaction(path) as db:
        row = db.execute('SELECT value FROM recovery WHERE id=1').fetchone()
        if row:
            state = json.loads(row[0])
            if state['anchor'] != snapshot:
                raise ValueError('store was initialized from a different snapshot')
        else:
            state = dict(anchor=copy.deepcopy(snapshot), version=0, frontier=copy.deepcopy(snapshot['frontier']),
                         values=copy.deepcopy(snapshot['values']), processed={t: 'commit' for t in snapshot['applied']},
                         events={}, decisions={}, requests={})
            save(db, state)
        return summary(state)


def inspect(path):
    with transaction(path) as db:
        return summary(load(db))


def replayed(state, request_id, payload, expected_version):
    """Original response for an exact repeat (checked before CAS); None for a new request."""
    if request_id in state['requests']:
        previous = state['requests'][request_id]
        return copy.deepcopy(previous['response'])
    if expected_version != state['version']:
        raise ValueError('store version changed')
    return None


def finish(db, state, request_id, payload, extra):
    state['version'] += 1
    response = {**summary(state), **extra}
    state['requests'][request_id] = {'payload': payload, 'response': copy.deepcopy(response)}
    save(db, state)
    return response
