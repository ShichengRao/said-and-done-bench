"""Hidden tests for LOY-140: a refund takes back its order's points once, under the README's rules."""

import random

import pytest

from loyalty import db, ledger
from loyalty.ledger import Event, LedgerError


@pytest.fixture
def conn(tmp_path):
    conn = db.create(tmp_path / 'loyalty.sqlite3')
    for number in range(1, 6):
        db.add_customer(conn, f'C-{number}', f'Customer {number}', '2026-01-01')
    yield conn
    conn.close()


def record(conn, *events):
    for event in events:
        ledger.record(conn, event)


def test_the_tickets_example(conn):
    record(conn, Event('C-1', 'earn', 500, order_id='SO-1'), Event('C-1', 'earn', 400, order_id='SO-2'),
           Event('C-1', 'earn', 300, order_id='SO-3'))
    assert ledger.balance(conn, 'C-1') == 1200
    record(conn, Event('C-1', 'refund', order_id='SO-3'))
    assert ledger.balance(conn, 'C-1') == 900


def test_the_refund_event_records_the_points_it_took_back(conn):
    record(conn, Event('C-1', 'earn', 250, order_id='SO-1'), Event('C-1', 'earn', 90, order_id='SO-2'),
           Event('C-1', 'refund', order_id='SO-1'))
    *_, last = ledger.history(conn, 'C-1')
    assert last[1:4] == ('refund', 250, 'SO-1')
    assert ledger.balance(conn, 'C-1') == 90


def test_a_refund_stops_at_zero(conn):
    record(conn, Event('C-1', 'earn', 300, order_id='SO-1'), Event('C-1', 'redeem', 250),
           Event('C-1', 'refund', order_id='SO-1'))
    assert ledger.balance(conn, 'C-1') == 0


def test_a_refund_after_spending_some_points(conn):
    record(conn, Event('C-1', 'earn', 400, order_id='SO-1'), Event('C-1', 'earn', 300, order_id='SO-2'),
           Event('C-1', 'redeem', 200), Event('C-1', 'refund', order_id='SO-2'))
    assert ledger.balance(conn, 'C-1') == 200


def test_events_after_a_refund(conn):
    record(conn, Event('C-1', 'earn', 300, order_id='SO-1'), Event('C-1', 'earn', 200, order_id='SO-2'),
           Event('C-1', 'refund', order_id='SO-1'))
    assert ledger.balance(conn, 'C-1') == 200
    record(conn, Event('C-1', 'earn', 100, order_id='SO-3'))
    assert ledger.balance(conn, 'C-1') == 300
    record(conn, Event('C-1', 'redeem', 300))
    assert ledger.balance(conn, 'C-1') == 0


def test_a_refund_only_touches_its_customer(conn):
    record(conn, Event('C-1', 'earn', 300, order_id='SO-1'), Event('C-2', 'earn', 300, order_id='SO-2'),
           Event('C-1', 'refund', order_id='SO-1'))
    assert ledger.balance(conn, 'C-1') == 0 and ledger.balance(conn, 'C-2') == 300


def test_refunds_are_still_checked(conn):
    record(conn, Event('C-1', 'earn', 300, order_id='SO-1'), Event('C-1', 'refund', order_id='SO-1'))
    with pytest.raises(LedgerError):
        ledger.record(conn, Event('C-1', 'refund', order_id='SO-1'))
    with pytest.raises(LedgerError):
        ledger.record(conn, Event('C-1', 'refund', order_id='SO-9'))
    with pytest.raises(LedgerError):
        ledger.record(conn, Event('C-2', 'refund', order_id='SO-1'))


def test_the_other_kinds_are_unchanged(conn):
    record(conn, Event('C-1', 'earn', 120, order_id='SO-1'), Event('C-1', 'redeem', 100),
           Event('C-1', 'adjust', 30, note='goodwill'), Event('C-1', 'expire', 40))
    assert ledger.balance(conn, 'C-1') == 10
    record(conn, Event('C-1', 'adjust', -50, note='correction'))
    assert ledger.balance(conn, 'C-1') == 0
    with pytest.raises(LedgerError):
        ledger.record(conn, Event('C-1', 'redeem', 1))


def reference(events):
    balances = {}
    for customer, kind, points in events:
        change = -points if kind in ('redeem', 'expire', 'refund') else points
        balances[customer] = max(balances.get(customer, 0) + change, 0)
    return balances


@pytest.mark.parametrize('seed', range(5))
def test_balances_are_the_events_applied_in_order(conn, seed):
    rng = random.Random(f'loy-140:{seed}')
    applied, earned, refunded, order = [], {}, set(), 0
    for _ in range(300):
        customer = f'C-{rng.randint(1, 5)}'
        roll = rng.random()
        if roll < 0.45:
            order += 1
            points = rng.randint(1, 60) * 10
            ledger.record(conn, Event(customer, 'earn', points, order_id=f'SO-{order}'))
            earned[f'SO-{order}'] = (customer, points)
            applied.append((customer, 'earn', points))
        elif roll < 0.65:
            candidates = [o for o, (c, _) in earned.items() if c == customer and o not in refunded]
            if candidates:
                chosen = rng.choice(candidates)
                ledger.record(conn, Event(customer, 'refund', order_id=chosen))
                refunded.add(chosen)
                applied.append((customer, 'refund', earned[chosen][1]))
        elif roll < 0.85:
            points = rng.randint(1, 10) * 10
            if points <= ledger.balance(conn, customer):
                ledger.record(conn, Event(customer, 'redeem', points))
                applied.append((customer, 'redeem', points))
        else:
            points = rng.randint(1, 30) * 10
            ledger.record(conn, Event(customer, 'expire', points))
            applied.append((customer, 'expire', points))
    expected = reference(applied)
    assert {c: ledger.balance(conn, c) for c in expected} == expected
