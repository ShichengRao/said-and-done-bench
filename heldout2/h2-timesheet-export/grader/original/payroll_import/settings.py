"""Where the import reads from and writes to."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The timesheet team's nightly export.
SOURCE = ROOT / 'out' / 'timesheets.csv'
# Hours waiting for the next pay run.
DATABASE = ROOT / 'var' / 'payroll-hours.sqlite3'
