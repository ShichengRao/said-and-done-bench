"""Loading the export into Payroll's hours database."""

import csv
import sqlite3

from payroll_import.fields import FieldError, day_month_year, employee_id, hours, project

COLUMNS = [('employee_id', employee_id), ('date', day_month_year), ('project', project), ('hours', hours)]


class ExportError(Exception):
    pass


def read(path):
    """(rows, problems): the parsed rows, and a message for each row that had to be skipped."""
    with open(path, newline='', encoding='utf-8') as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        expected = [name for name, _ in COLUMNS]
        if header != expected:
            raise ExportError(f'the export has columns {header}, expected {expected}')
        rows, problems = [], []
        for number, record in enumerate(reader, start=2):
            if len(record) != len(COLUMNS):
                problems.append(f'line {number}: {len(record)} fields, expected {len(COLUMNS)}')
                continue
            try:
                rows.append(tuple(parse(value) for (_, parse), value in zip(COLUMNS, record)))
            except FieldError as error:
                problems.append(f'line {number}: {error}')
    return rows, problems


def store(rows, database):
    database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database)
    with conn:
        conn.execute('CREATE TABLE IF NOT EXISTS hours (employee_id TEXT, day TEXT, project TEXT, hours TEXT, '
                     'PRIMARY KEY (employee_id, day, project))')
        conn.executemany('INSERT OR REPLACE INTO hours VALUES (?, ?, ?, ?)',
                         [(e, d.isoformat(), p, str(h)) for e, d, p, h in rows])
    conn.close()
