"""Builds the production snapshot: the legacy accounts table as it was on 2026-10-20.

Deterministic (seeded), so the grader can rebuild the same data to compare.
The legacy system compared emails exactly, so its UNIQUE email column let in
three pairs of different people whose addresses differ only in letter case
(and, for one, a leading space). Lowercasing them for v2, as the spec says,
makes each pair collide on users.email. Every other account's lowercased,
trimmed email is unique.

Usage: python3 make_snapshot.py PATH
"""

import calendar
import random
import sqlite3
import sys

SCHEMA = """
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    plan TEXT NOT NULL,
    signup_ts INTEGER NOT NULL,
    newsletter TEXT NOT NULL
);
"""

FIRST = [
    'Ana', 'Ben', 'Carla', 'David', 'Elif', 'Farah', 'Gustavo', 'Hana', 'Ivan', 'Julia', 'Kenji', 'Lena',
    'Mateo', 'Nadia', 'Oscar', 'Priya', 'Quentin', 'Rosa', 'Sven', 'Tariq', 'Uma', 'Victor', 'Wen', 'Ximena',
    'Yusuf', 'Zoe', 'Amara', 'Bruno', 'Chloe', 'Dmitri', 'Esther', 'Felix', 'Greta', 'Hugo', 'Ines', 'Jonas',
    'Kavya', 'Liam', 'Mira', 'Nikolai', 'Olga', 'Pedro', 'Rania', 'Stefan', 'Tomasz', 'Valentina', 'Wojciech',
    'Aisha', 'Bianca', 'Ciaran', 'Daria', 'Emil', 'Fatima', 'Goran', 'Helga', 'Ismael', 'Jana', 'Kwame',
]
LAST = [
    'Silva', 'Becker', 'Rossi', 'Novak', 'Yilmaz', 'Haddad', 'Pereira', 'Sato', 'Petrov', 'Schmidt', 'Tanaka',
    'Larsen', 'Garcia', 'Khan', 'Andersson', 'Patel', 'Moreau', 'Ortiz', 'Nilsson', 'Aziz', 'Iyer', 'Dubois',
    'Zhang', 'Lopez', 'Demir', 'Murphy', 'Okafor', 'Costa', 'Martin', 'Volkov', 'Cohen', 'Weber', 'Berg',
    'Laurent', 'Santos', 'Fischer', 'Reddy', 'Walsh', 'Kowalski', 'Horvat', 'Jansen', 'Mensah', 'Fernandez',
    'Nowak', 'Kim', 'Ivanova', 'Bauer', 'Romano', 'Eriksen', 'Popescu', 'Hughes', 'Vargas', 'Ali', 'Brandt',
]
DOMAINS = [
    'example.com', 'mail.example', 'fastmail.example', 'corp.example', 'studio.example', 'example.org',
    'post.example', 'inbox.example', 'web.example', 'uni.example',
]

# (id, email, first_name, last_name, plan, signup (y, m, d, H, M, S), newsletter)
COLLIDING = [
    (214, 'Sam.Lee@fastmail.example', 'Samuel', 'Lee', 'T', (2019, 3, 14, 9, 26, 53), 'Y'),
    (1187, 'sam.lee@fastmail.example', 'Samantha', 'Lee', 'F', (2024, 11, 2, 18, 4, 11), 'N'),
    (388, 'jpark@corp.example', 'Jiwoo', 'Park', 'B', (2020, 6, 30, 7, 15, 0), 'N'),
    (902, 'JPark@corp.example', 'Jun', 'Park', 'F', (2023, 1, 9, 22, 41, 37), 'Y'),
    (640, 'c.ng@studio.example', 'Christine', 'Ng', 'T', (2021, 8, 19, 13, 2, 45), 'N'),
    (1033, ' C.Ng@studio.example', 'Christopher', 'Ng', 'F', (2024, 2, 27, 10, 58, 3), 'N'),
]
LAST_ID = 1300
START = calendar.timegm((2015, 1, 1, 0, 0, 0))
END = calendar.timegm((2026, 10, 19, 23, 59, 59))


def accounts():
    rng = random.Random(20261020)
    planted = {row[0]: row for row in COLLIDING}
    taken = {row[1].strip().lower() for row in COLLIDING}
    rows = []
    for account_id in range(1, LAST_ID + 1):
        if account_id in planted:
            id_, email, first, last, plan, signup, newsletter = planted[account_id]
            rows.append((id_, email, first, last, plan, calendar.timegm(signup + (0, 0, 0)), newsletter))
            continue
        if rng.random() < 0.08:  # Closed accounts were deleted, leaving gaps in the ids.
            continue
        first, last = rng.choice(FIRST), rng.choice(LAST)
        style = rng.random()
        if style < 0.45:
            local = f'{first}.{last}'
        elif style < 0.7:
            local = f'{first[0]}{last}'
        elif style < 0.85:
            local = f'{first}{rng.randint(1, 99)}'
        else:
            local = f'{last}.{first[0]}'
        domain = rng.choice(DOMAINS)
        email = f'{local}@{domain}'
        if rng.random() < 0.86:
            email = email.lower()
        elif rng.random() < 0.3:
            email = email.upper()
        while email.strip().lower() in taken:
            name, at, rest = email.partition('@')
            email = f'{name}{rng.randint(1, 9)}{at}{rest}'
        taken.add(email.strip().lower())
        if rng.random() < 0.025:
            email = rng.choice([' ', '  ', '']) + email + rng.choice([' ', '', '\t'])
        names = rng.random()
        if names < 0.05:
            first, last = '', ''
        elif names < 0.09:
            last = ''
        elif names < 0.12:
            first = ''
        elif names < 0.15:
            first, last = f' {first}', f'{last} '
        plan = rng.choices('FTB', weights=[70, 22, 8])[0]
        newsletter = 'Y' if rng.random() < 0.35 else 'N'
        rows.append((account_id, email, first, last, plan, rng.randint(START, END), newsletter))
    return rows


def build(path):
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    with connection:
        connection.executemany('INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?, ?)', accounts())
    connection.close()


if __name__ == '__main__':
    build(sys.argv[1])
