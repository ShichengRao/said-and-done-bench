import os
import subprocess
import sys
from pathlib import Path

import pytest

from loyalty import db, ledger

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def database(tmp_path):
    location = tmp_path / 'loyalty.sqlite3'
    conn = db.create(location)
    db.add_customer(conn, 'C-1', 'Ada Lind', '2026-01-05')
    ledger.record(conn, ledger.Event('C-1', 'earn', 120, order_id='SO-1', at='2026-03-01T10:00:00Z'))
    conn.close()
    return location


def cli(database, *args):
    return subprocess.run([sys.executable, '-m', 'loyalty', *args], cwd=ROOT, capture_output=True, text=True,
                          env={**os.environ, 'LOYALTY_DB': str(database)})


def test_balance(database):
    result = cli(database, 'balance', 'C-1')
    assert result.returncode == 0
    assert result.stdout == 'C-1 Ada Lind: 120 points\n'


def test_record_and_history(database):
    assert cli(database, 'record', 'redeem', 'C-1', '--points', '20').returncode == 0
    lines = cli(database, 'history', 'C-1').stdout.splitlines()
    assert 'earn' in lines[0] and 'SO-1' in lines[0]
    assert 'redeem' in lines[1]
    assert lines[-1] == 'balance: 100 points'


def test_unknown_customer(database):
    result = cli(database, 'balance', 'C-404')
    assert result.returncode == 1 and 'unknown customer' in result.stderr
