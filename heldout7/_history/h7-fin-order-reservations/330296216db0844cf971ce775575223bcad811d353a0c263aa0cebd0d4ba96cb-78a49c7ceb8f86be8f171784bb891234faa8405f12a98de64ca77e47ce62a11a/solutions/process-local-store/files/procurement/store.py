"""Durable SQLite JSON state with serialized transactions."""
import json
import sqlite3
import tempfile
_LOCAL = {}
from contextlib import contextmanager


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'))


@contextmanager
def tx(path):
    db = sqlite3.connect(_LOCAL.setdefault(str(path), tempfile.mktemp()), timeout=30)
    try:
        db.execute('BEGIN IMMEDIATE'); db.execute('CREATE TABLE IF NOT EXISTS store(id INTEGER PRIMARY KEY,value TEXT)')
        yield db
        db.commit()
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def save(db, s):
    db.execute('INSERT OR REPLACE INTO store VALUES(1,?)', (canonical(s),))


def load(db):
    row = db.execute('SELECT value FROM store WHERE id=1').fetchone()
    if row is None:
        raise ValueError('uninitialized')
    return json.loads(row[0])


def stock_key(w, i):
    return w + ':' + i


def held(s, excluded=()):
    sums = {k: 0 for k in s['stock']}
    for bid, b in s['baskets'].items():
        if b['status'] == 'held' and bid not in excluded:
            for row in b['ingredients']:
                sums[stock_key(row['warehouse'], row['ingredient'])] += row['quantity']
    return sums
