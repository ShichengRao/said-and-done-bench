"""The nightly export: one day's hours as CSV, one row per employee and project."""

import csv
import datetime as dt
from decimal import Decimal

COLUMNS = ['employee_id', 'date', 'project', 'hours']
DATE_FORMAT = '%d/%m/%Y'


def rows(conn, day):
    """(employee_id, day, project, hours) for one day, summed per employee and project, in a stable order."""
    found = conn.execute(
        'SELECT employee_id, project, SUM(minutes) FROM entries WHERE day = ? '
        'GROUP BY employee_id, project ORDER BY employee_id, project', (day.isoformat(),)).fetchall()
    return [(employee, day, project, Decimal(minutes) / 60) for employee, project, minutes in found]


def export(conn, day, out):
    """Write one day's hours to `out`. Returns how many rows were written."""
    written = rows(conn, day)
    with open(out, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for employee, when, project, hours in written:
            writer.writerow([employee, when.strftime(DATE_FORMAT), project, f'{hours:.2f}'])
    return len(written)


def yesterday():
    return dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
