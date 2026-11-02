"""Reading the legacy accounts table."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LegacyAccount:
    id: int
    email: str
    first_name: str
    last_name: str
    plan: str  # F, T, or B
    signup_ts: int  # Unix seconds
    newsletter: str  # Y or N


def read_accounts(path):
    """Every account in the legacy database at `path`, by id. Opens it read-only."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        rows = connection.execute(
            'SELECT id, email, first_name, last_name, plan, signup_ts, newsletter FROM accounts ORDER BY id'
        ).fetchall()
    finally:
        connection.close()
    return [LegacyAccount(*row) for row in rows]
