"""The hours staff log: data/timesheets.sqlite3 (TIMESHEETS_DB points somewhere else)."""

import os
import sqlite3
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / 'data' / 'timesheets.sqlite3'
SCHEMA = """
CREATE TABLE entries (
    id INTEGER PRIMARY KEY,
    employee_id TEXT NOT NULL,
    day TEXT NOT NULL,          -- ISO date
    project TEXT NOT NULL,
    minutes INTEGER NOT NULL,
    note TEXT
);
"""


def connect(path=None):
    location = Path(path or os.environ.get('TIMESHEETS_DB') or DEFAULT_PATH)
    if not location.exists():
        raise FileNotFoundError(f'no timesheet database at {location}')
    return sqlite3.connect(location)


def create(path):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def log(conn, employee_id, day, project, minutes, note=None):
    with conn:
        conn.execute('INSERT INTO entries (employee_id, day, project, minutes, note) VALUES (?, ?, ?, ?, ?)',
                     (employee_id, day.isoformat(), project, minutes, note))
