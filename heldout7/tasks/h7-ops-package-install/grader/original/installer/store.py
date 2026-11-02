"""SQLite-backed installer store. One row holds trust, metadata cache, installs and request log."""
import copy
import hashlib
import json
import sqlite3
from contextlib import contextmanager

from installer.crypto import canonical


@contextmanager
def transaction(path):
    """Serialized read-modify-write: BEGIN IMMEDIATE blocks other writers until commit."""
    db = sqlite3.connect(path, timeout=30)
    try:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS installs(id INTEGER PRIMARY KEY, value TEXT)')
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def save(db, state):
    db.execute('INSERT OR REPLACE INTO installs VALUES(1, ?)', (canonical(state).decode(),))


def load(db):
    row = db.execute('SELECT value FROM installs WHERE id=1').fetchone()
    if row is None:
        raise ValueError('store is not initialized')
    return json.loads(row[0])


def summary(state):
    return {'version': state['version'], 'at': state['at'], 'repositories': {
        name: {'root_version': repo['root']['version'], 'snapshot_version': repo['snapshot_version'],
               'roles': {role: info['version'] for role, info in repo['roles'].items()},
               'installed': {path: {'length': len(raw.encode()), 'sha256': hashlib.sha256(raw.encode()).hexdigest()}
                             for path, raw in repo['installed'].items()}}
        for name, repo in state['repos'].items()}}


def initialize(path, anchors):
    with transaction(path) as db:
        row = db.execute('SELECT value FROM installs WHERE id=1').fetchone()
        if row:
            state = json.loads(row[0])
            if state['anchors'] != anchors:
                raise ValueError('store was initialized with different trusted roots')
        else:
            state = {'anchors': copy.deepcopy(anchors), 'version': 0, 'at': -1, 'requests': {},
                     'repos': {name: {'root': copy.deepcopy(root), 'snapshot_version': 0, 'snapshot_digest': None,
                                      'roles': {}, 'installed': {}} for name, root in anchors.items()}}
            save(db, state)
        return summary(state)


def inspect(path):
    with transaction(path) as db:
        return summary(load(db))
