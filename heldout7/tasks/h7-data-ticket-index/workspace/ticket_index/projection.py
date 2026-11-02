"""Durable projection store (SQLite) shared by ingestion workers."""
import json
import sqlite3
from pathlib import Path

from . import state as index_state


class Projection:
    def __init__(self, path, initial=None):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS projection (id INTEGER PRIMARY KEY, state TEXT NOT NULL)')
            row = conn.execute('SELECT state FROM projection WHERE id = 1').fetchone()
            if row is None:
                if initial is None:
                    raise ValueError('a new projection store needs the initial snapshot')
                conn.execute('INSERT INTO projection VALUES (1, ?)', (json.dumps(index_state.new_state(initial)),))
            elif initial is not None and json.loads(row[0])['initial'] != initial:
                raise ValueError('store was created from a different initial snapshot')

    def _connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def _load(self):
        with self._connect() as conn:
            return json.loads(conn.execute('SELECT state FROM projection WHERE id = 1').fetchone()[0])

    def _save(self, value):
        with self._connect() as conn:
            conn.execute('UPDATE projection SET state = ? WHERE id = 1', (json.dumps(value),))

    def ingest(self, messages):
        for message in messages:
            self._save(index_state.accept(self._load(), [message]))
        return self.status()

    def status(self):
        return index_state.status(self._load())

    def query(self, epoch, user):
        return index_state.query(self._load(), epoch, user)
