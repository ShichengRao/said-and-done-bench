"""Recording loyalty events and keeping each customer's balance.

Every change to a customer's points is an event in the `events` table, the
audit trail. `balances` holds each customer's current points, and record()
updates it as it records each event. The rules are in README.md.
"""

import dataclasses
import datetime as dt

KINDS = ('earn', 'redeem', 'adjust', 'expire')
# Kinds whose points come off the balance.
DEBITS = ('redeem', 'expire')


class LedgerError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class Event:
    customer: str
    kind: str
    points: int = 0
    order_id: str | None = None
    note: str | None = None
    at: str | None = None  # ISO 8601, UTC; now if not given


def now():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def balance(conn, customer):
    row = conn.execute('SELECT points FROM balances WHERE customer = ?', (customer,)).fetchone()
    return row[0] if row else 0


def record(conn, event):
    """Check an event, add it to the log, and update the customer's balance. Returns the event's id."""
    if event.kind not in KINDS:
        raise LedgerError(f'unknown kind of event: {event.kind!r}')
    if conn.execute('SELECT 1 FROM customers WHERE id = ?', (event.customer,)).fetchone() is None:
        raise LedgerError(f'unknown customer {event.customer}')
    if event.kind == 'adjust':
        if event.points == 0 or not event.note:
            raise LedgerError('an adjustment needs non-zero points and a note')
    elif event.points <= 0:
        raise LedgerError(f'{event.kind} points must be positive')
    if event.kind == 'earn' and not event.order_id:
        raise LedgerError('earned points need the order they were earned on')
    if event.kind == 'redeem' and event.points > balance(conn, event.customer):
        raise LedgerError(f'{event.customer} has only {balance(conn, event.customer)} points')
    event = dataclasses.replace(event, at=event.at or now())
    with conn:
        cursor = conn.execute(
            'INSERT INTO events (customer, kind, points, order_id, note, at) VALUES (?, ?, ?, ?, ?, ?)',
            (event.customer, event.kind, event.points, event.order_id, event.note, event.at),
        )
        _update_balance(conn, event)
    return cursor.lastrowid


def _update_balance(conn, event):
    points = balance(conn, event.customer)
    if event.kind in DEBITS:
        points -= event.points
    else:
        points += event.points
    points = max(points, 0)  # A balance never goes below zero.
    conn.execute(
        'INSERT INTO balances (customer, points, updated_at) VALUES (?, ?, ?) '
        'ON CONFLICT(customer) DO UPDATE SET points = excluded.points, updated_at = excluded.updated_at',
        (event.customer, points, event.at),
    )


def history(conn, customer):
    return conn.execute('SELECT id, kind, points, order_id, note, at FROM events WHERE customer = ? ORDER BY id',
                        (customer,)).fetchall()
