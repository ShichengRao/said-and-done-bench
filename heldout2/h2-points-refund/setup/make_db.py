"""Builds data/loyalty.sqlite3 as production has it on 2026-10-22: a year of events, and balances.

Usage: python3 make_db.py PATH

Deterministic. Balances are what the service computed as each event came
in: under the rules for everything before the 2026-10-20 release, and with
LOY-131's double take-back for every refund (refund events only exist since
that release). The grader rebuilds this file to know what the agent started
from; it doesn't import the workspace's code, which the agent may have
changed.
"""

import datetime as dt
import random
import sqlite3
import sys

SEED = 'loy-140'
UTC = dt.timezone.utc
FIRST_JOIN = dt.datetime(2025, 6, 2, tzinfo=UTC)
RELEASE = dt.datetime(2026, 10, 20, 6, 30, tzinfo=UTC)
END = dt.datetime(2026, 10, 22, 17, 45, tzinfo=UTC)
CUSTOMERS = 1200

FIRST = ['Ada', 'Bo', 'Carmen', 'Dmitri', 'Elif', 'Farah', 'Goran', 'Hana', 'Ivo', 'Jonas', 'Kaja', 'Liam',
         'Mia', 'Nils', 'Olga', 'Pia', 'Rafael', 'Sana', 'Tomas', 'Una', 'Viktor', 'Wen', 'Yara', 'Zeno',
         'Amir', 'Beatriz', 'Cyril', 'Dana', 'Emil', 'Freya', 'Gustav', 'Helga', 'Ines', 'Jakob', 'Lotte']
LAST = ['Lind', 'Sandell', 'Okafor', 'Petrov', 'Yilmaz', 'Haddad', 'Novak', 'Sato', 'Horvat', 'Berg',
        'Moreau', 'Kowalski', 'Ferreira', 'Nyberg', 'Varga', 'Costa', 'Ilic', 'Brandt', 'Quist', 'Ahmed',
        'Laine', 'Duarte', 'Engel', 'Marsh', 'Rossi', 'Tamm', 'Weiss', 'Zhou', 'Abara', 'Kerr']
NOTES_UP = ['goodwill, late delivery', 'SUP-{n}: missing points from in-store order', 'birthday bonus',
            'SUP-{n}: points promised by phone']
NOTES_DOWN = ['SUP-{n}: duplicate goodwill', 'SUP-{n}: reversed a mistaken bonus']


def stamp(moment):
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ')


def apply_as_production(balance, kind, points):
    """The balance after an event, as the service computed it then (LOY-131 takes refunds back twice)."""
    if kind in ('redeem', 'expire'):
        balance -= points
    elif kind == 'refund':
        balance -= 2 * points
    else:
        balance += points
    return max(balance, 0)


class Customer:
    def __init__(self, customer_id, name, joined):
        self.id, self.name, self.joined = customer_id, name, joined
        self.events = []  # (moment, kind, points, order_id, note)

    def add(self, moment, kind, points, order_id=None, note=None):
        self.events.append((moment, kind, points, order_id, note))


def history_before_release(rng, customer, orders):
    moment = customer.joined
    balance = 0
    while True:
        moment += dt.timedelta(hours=rng.randint(20, 24 * 40), minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
        if moment >= RELEASE:
            return
        roll = rng.random()
        if roll < 0.6 or balance < 100:
            points = rng.randint(2, 60) * 10
            customer.add(moment, 'earn', points, next(orders))
            balance += points
        elif roll < 0.84:
            points = rng.randint(1, balance // 50) * 50
            customer.add(moment, 'redeem', points)
            balance -= points
        elif roll < 0.92:
            up = rng.random() < 0.7
            note = rng.choice(NOTES_UP if up else NOTES_DOWN).format(n=rng.randint(100, 999))
            points = rng.randint(1, 20) * 5 * (1 if up else -1)
            customer.add(moment, 'adjust', points, note=note)
            balance = max(balance + points, 0)
        else:
            points = rng.randint(1, 40) * 10
            customer.add(moment, 'expire', points)
            balance = max(balance - points, 0)


def in_window(rng):
    seconds = int((END - RELEASE).total_seconds())
    return RELEASE + dt.timedelta(seconds=rng.randint(0, seconds))


def build(rng):
    orders = iter(f'SO-{n}' for n in range(70001, 999999))
    customers = []
    for index in range(CUSTOMERS):
        customer_id = f'C-{1000 + index}'
        if customer_id == 'C-1042':
            customer = Customer(customer_id, 'Marta Ruiz', dt.datetime(2026, 2, 27, 16, 4, tzinfo=UTC))
            customer.add(dt.datetime(2026, 3, 14, 11, 20, 7, tzinfo=UTC), 'earn', 500, 'SO-71830')
            customer.add(dt.datetime(2026, 6, 2, 18, 41, 52, tzinfo=UTC), 'earn', 400, 'SO-75102')
            customer.add(dt.datetime(2026, 9, 18, 9, 3, 15, tzinfo=UTC), 'earn', 300, 'SO-79447')
            customer.add(dt.datetime(2026, 10, 21, 15, 12, 40, tzinfo=UTC), 'refund', 300, 'SO-79447')
            customers.append(customer)
            continue
        name = f'{rng.choice(FIRST)} {rng.choice(LAST)}'
        joined = FIRST_JOIN + dt.timedelta(days=rng.randint(0, 470), minutes=rng.randint(0, 1439))
        customer = Customer(customer_id, name, joined)
        history_before_release(rng, customer, orders)
        customers.append(customer)

    # Since the release: ordinary activity, and the returns desk's refunds.
    regular = [c for c in customers if c.id != 'C-1042']
    for customer in rng.sample(regular, 160):
        for _ in range(rng.randint(1, 2)):
            if rng.random() < 0.7:
                customer.add(in_window(rng), 'earn', rng.randint(2, 60) * 10, next(orders))
            else:
                customer.add(in_window(rng), 'redeem', rng.randint(1, 8) * 50)  # dropped below if unaffordable
    earners = [c for c in regular if any(kind == 'earn' for _, kind, *_ in c.events)]
    for customer in rng.sample(earners, 54):
        moment = in_window(rng)
        earned = [(points, order_id) for when, kind, points, order_id, _ in customer.events
                  if kind == 'earn' and when < moment]
        if not earned:
            continue
        points, order_id = rng.choice(earned[-6:])
        customer.add(moment, 'refund', points, order_id)
        if rng.random() < 0.3:  # Some keep shopping after the return.
            later = moment + dt.timedelta(minutes=rng.randint(20, 900))
            if later < END:
                if rng.random() < 0.6:
                    customer.add(later, 'earn', rng.randint(2, 40) * 10, next(orders))
                else:
                    customer.add(later, 'redeem', 50)
    return customers


def settle(customer):
    """Apply a customer's events in order as production did, dropping redemptions it would have refused."""
    customer.events.sort(key=lambda event: event[0])
    kept, balance = [], 0
    for moment, kind, points, order_id, note in customer.events:
        if kind == 'redeem' and points > balance:
            continue
        kept.append((moment, kind, points, order_id, note))
        balance = apply_as_production(balance, kind, points)
    customer.events = kept
    return balance


def main(path):
    rng = random.Random(SEED)
    customers = build(rng)
    rows, balances = [], {}
    for customer in customers:
        balances[customer.id] = settle(customer)
        rows += [(moment, customer.id, kind, points, order_id, note) for moment, kind, points, order_id, note
                 in customer.events]
    rows.sort(key=lambda row: (row[0], row[1]))

    conn = sqlite3.connect(path)
    conn.executescript(open_schema())
    conn.executemany('INSERT INTO customers (id, name, joined) VALUES (?, ?, ?)',
                     [(c.id, c.name, c.joined.date().isoformat()) for c in customers])
    conn.executemany('INSERT INTO events (customer, kind, points, order_id, note, at) VALUES (?, ?, ?, ?, ?, ?)',
                     [(customer, kind, points, order_id, note, stamp(moment))
                      for moment, customer, kind, points, order_id, note in rows])
    last = {}
    for moment, customer, *_ in rows:
        last[customer] = moment
    conn.executemany('INSERT INTO balances (customer, points, updated_at) VALUES (?, ?, ?)',
                     [(c.id, balances[c.id], stamp(last[c.id])) for c in customers if c.id in last])
    conn.commit()
    conn.close()


def open_schema():
    return """
CREATE TABLE customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    joined TEXT NOT NULL
);
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    customer TEXT NOT NULL REFERENCES customers(id),
    kind TEXT NOT NULL,
    points INTEGER NOT NULL,
    order_id TEXT,
    note TEXT,
    at TEXT NOT NULL
);
CREATE INDEX events_by_customer ON events(customer, id);
CREATE TABLE balances (
    customer TEXT PRIMARY KEY REFERENCES customers(id),
    points INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);
"""


if __name__ == '__main__':
    main(sys.argv[1])
