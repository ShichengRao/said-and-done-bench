import csv
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

import pytest

from timesheets import export, store

ROOT = Path(__file__).resolve().parent.parent
DAY = dt.date(2026, 10, 22)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'timesheets.sqlite3'
    conn = store.create(path)
    store.log(conn, 'E10477', DAY, 'ATLAS', 240)
    store.log(conn, 'E10231', DAY, 'SUPPORT', 30)
    store.log(conn, 'E10231', DAY, 'ATLAS', 450)
    store.log(conn, 'E10477', DAY, 'ATLAS', 225)
    store.log(conn, 'E10231', DAY - dt.timedelta(days=1), 'ATLAS', 480)
    conn.close()
    return path


def test_export(database, tmp_path):
    out = tmp_path / 'timesheets.csv'
    assert export.export(store.connect(database), DAY, out) == 3
    with open(out, newline='') as handle:
        assert list(csv.reader(handle)) == [
            ['employee_id', 'date', 'project', 'hours'],
            ['E10231', '22/10/2026', 'ATLAS', '7.50'],
            ['E10231', '22/10/2026', 'SUPPORT', '0.50'],
            ['E10477', '22/10/2026', 'ATLAS', '7.75'],
        ]


def test_a_day_without_hours(database, tmp_path):
    out = tmp_path / 'timesheets.csv'
    assert export.export(store.connect(database), dt.date(2026, 10, 25), out) == 0
    assert out.read_text() == 'employee_id,date,project,hours\n'


def test_the_command(database, tmp_path):
    out = tmp_path / 'out.csv'
    result = subprocess.run([sys.executable, '-m', 'timesheets', 'export', '--day', '2026-10-22', '--out', str(out)],
                            cwd=ROOT, capture_output=True, text=True, env={**os.environ, 'TIMESHEETS_DB': str(database)})
    assert result.returncode == 0 and result.stdout.startswith('exported 3 rows for 2026-10-22')
    assert out.read_text().splitlines()[1] == 'E10231,22/10/2026,ATLAS,7.50'
