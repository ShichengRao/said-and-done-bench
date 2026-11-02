"""The loyalty database: customers, the event log, and each customer's balance."""

import os
import sqlite3
from pathlib import Path

# The service's database; LOYALTY_DB points somewhere else (the tests use it).
DEFAULT_PATH = Path(__file__).resolve().parent.parent / 'data' / 'loyalty.sqlite3'

SCHEMA = """
CREATE TABLE customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    joined TEXT NOT NULL
);
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    customer TEXT NOT NULL REFERENCES customers(id),
    kind TEXT NOT NULL,
    points INTEGER NOT NULL,
    order_id TEXT,
    note TEXT,
    at TEXT NOT NULL
);
CREATE INDEX events_by_customer ON events(customer, id);
CREATE TABLE balances (
    customer TEXT PRIMARY KEY REFERENCES customers(id),
    points INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def path():
    return Path(os.environ.get('LOYALTY_DB') or DEFAULT_PATH)


def connect(location=None):
    location = Path(location) if location else path()
    if not location.exists():
        raise FileNotFoundError(f'no loyalty database at {location}')
    return sqlite3.connect(location)


def create(location):
    """A new, empty database (for tests and new environments)."""
    conn = sqlite3.connect(location)
    conn.executescript(SCHEMA)
    return conn


def add_customer(conn, customer_id, name, joined):
    with conn:
        conn.execute('INSERT INTO customers (id, name, joined) VALUES (?, ?, ?)', (customer_id, name, joined))
