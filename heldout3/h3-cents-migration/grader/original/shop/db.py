"""The shop's database."""

import os
import sqlite3
from pathlib import Path

# Production's database; SHOP_DB points somewhere else (the tests use it).
DEFAULT_PATH = Path(__file__).resolve().parent.parent / 'data' / 'shop.sqlite3'


def path():
    return Path(os.environ.get('SHOP_DB') or DEFAULT_PATH)


def connect(location=None):
    """A connection to the database (a new, empty one if the file doesn't exist yet)."""
    conn = sqlite3.connect(Path(location) if location else path())
    conn.row_factory = sqlite3.Row
    return conn
