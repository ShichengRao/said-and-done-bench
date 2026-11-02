"""Reading the time clock's CSV export into shifts per employee."""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

from payroll.overtime import Shift

TIME_FORMAT = '%Y-%m-%d %H:%M'


def parse_time(text: str) -> dt.datetime:
    return dt.datetime.strptime(text.strip(), TIME_FORMAT)


def load_timesheet(path: Path) -> dict[str, list[Shift]]:
    """Shifts by employee id, from rows of `employee,start,end`."""
    shifts: dict[str, list[Shift]] = {}
    with open(path, newline='', encoding='utf-8') as handle:
        for row in csv.DictReader(handle):
            shift = Shift(parse_time(row['start']), parse_time(row['end']))
            shifts.setdefault(row['employee'].strip(), []).append(shift)
    return shifts
