import datetime as dt
import os
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from payroll_import.fields import FieldError, day_month_year, hours
from payroll_import.load import ExportError, read

FIXTURES = Path(__file__).resolve().parent / 'fixtures'
ROOT = Path(__file__).resolve().parent.parent.parent


def test_reading_the_export():
    rows, problems = read(FIXTURES / 'timesheets.csv')
    assert problems == []
    assert rows[0] == ('E10231', dt.date(2026, 10, 14), 'ATLAS', Decimal('7.50'))
    assert len(rows) == 4


def test_fields():
    assert day_month_year('03/11/2026') == dt.date(2026, 11, 3)
    for bad in ('3/11/2026', '31/02/2026', '2026/11/03'):
        with pytest.raises(FieldError):
            day_month_year(bad)
    with pytest.raises(FieldError):
        hours('25')


def test_rows_that_do_not_parse_are_skipped(tmp_path):
    export = tmp_path / 'timesheets.csv'
    export.write_text('employee_id,date,project,hours\nE10231,14/10/2026,ATLAS,7.50\nX1,14/10/2026,ATLAS,1\n')
    rows, problems = read(export)
    assert len(rows) == 1 and problems == ["line 3: employee id 'X1' should be E and five digits"]


def test_the_columns_are_checked(tmp_path):
    export = tmp_path / 'timesheets.csv'
    export.write_text('employee,date,project,hours\n')
    with pytest.raises(ExportError):
        read(export)


def test_the_command(tmp_path):
    copy = tmp_path / 'repo'
    shutil.copytree(ROOT / 'payroll_import', copy / 'payroll_import', ignore=shutil.ignore_patterns('__pycache__'))
    result = subprocess.run([sys.executable, '-m', 'payroll_import', str(FIXTURES / 'timesheets.csv')], cwd=copy,
                            capture_output=True, text=True, env={**os.environ, 'PYTHONPATH': str(copy)})
    assert result.returncode == 0 and result.stdout.endswith('loaded 4 rows from '
                                                              f"{FIXTURES / 'timesheets.csv'} (0 skipped)\n")
    assert (copy / 'var' / 'payroll-hours.sqlite3').exists()
