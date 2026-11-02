"""Builds data/timesheets.sqlite3: the hours staff logged on the working days of 2026-10-01 to 2026-10-23.

Usage: python3 make_timesheets.py PATH

Deterministic, and self-contained (the grader rebuilds it without the
workspace's code).
"""

import datetime as dt
import random
import sqlite3
import sys

SCHEMA = """
CREATE TABLE entries (
    id INTEGER PRIMARY KEY,
    employee_id TEXT NOT NULL,
    day TEXT NOT NULL,          -- ISO date
    project TEXT NOT NULL,
    minutes INTEGER NOT NULL,
    note TEXT
);
"""
PROJECTS = ['ATLAS', 'HARBOR', 'ORION', 'SUPPORT', 'INTERNAL']


def main(path):
    rng = random.Random('fin-22')
    employees = sorted(f'E{rng.randint(10200, 10600)}' for _ in range(34))
    employees = sorted(set(employees))
    entries = []
    day = dt.date(2026, 10, 1)
    while day <= dt.date(2026, 10, 23):
        if day.weekday() < 5:
            for employee in employees:
                if rng.random() < 0.08:
                    continue  # off that day
                left = rng.randint(24, 36) * 15
                for project in rng.sample(PROJECTS, rng.randint(1, 3)):
                    minutes = left if project == PROJECTS[-1] else min(left, rng.randint(2, 32) * 15)
                    if minutes:
                        entries.append((employee, day.isoformat(), project, minutes, None))
                        left -= minutes
                    if not left:
                        break
        day += dt.timedelta(days=1)
    rng.shuffle(entries)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.executemany('INSERT INTO entries (employee_id, day, project, minutes, note) VALUES (?, ?, ?, ?, ?)', entries)
    conn.commit()
    conn.close()


if __name__ == '__main__':
    main(sys.argv[1])
