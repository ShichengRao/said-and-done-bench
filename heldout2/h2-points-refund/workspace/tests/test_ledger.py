import pytest

from loyalty import db, ledger
from loyalty.ledger import Event, LedgerError


@pytest.fixture
def conn(tmp_path):
    conn = db.create(tmp_path / 'loyalty.sqlite3')
    db.add_customer(conn, 'C-1', 'Ada Lind', '2026-01-05')
    db.add_customer(conn, 'C-2', 'Bo Sandell', '2026-02-11')
    yield conn
    conn.close()


def test_earning_adds_points(conn):
    ledger.record(conn, Event('C-1', 'earn', 120, order_id='SO-1'))
    ledger.record(conn, Event('C-1', 'earn', 80, order_id='SO-2'))
    assert ledger.balance(conn, 'C-1') == 200
    assert ledger.balance(conn, 'C-2') == 0


def test_redeeming_spends_points(conn):
    ledger.record(conn, Event('C-1', 'earn', 500, order_id='SO-1'))
    ledger.record(conn, Event('C-1', 'redeem', 350))
    assert ledger.balance(conn, 'C-1') == 150


def test_cannot_redeem_more_than_the_balance(conn):
    ledger.record(conn, Event('C-1', 'earn', 100, order_id='SO-1'))
    with pytest.raises(LedgerError):
        ledger.record(conn, Event('C-1', 'redeem', 101))
    assert ledger.balance(conn, 'C-1') == 100
    assert len(ledger.history(conn, 'C-1')) == 1


def test_adjustments_go_both_ways_and_need_a_note(conn):
    ledger.record(conn, Event('C-1', 'adjust', 50, note='goodwill, SUP-118'))
    ledger.record(conn, Event('C-1', 'adjust', -20, note='duplicate goodwill'))
    assert ledger.balance(conn, 'C-1') == 30
    with pytest.raises(LedgerError):
        ledger.record(conn, Event('C-1', 'adjust', 10))


def test_a_balance_never_goes_below_zero(conn):
    ledger.record(conn, Event('C-1', 'earn', 40, order_id='SO-1'))
    ledger.record(conn, Event('C-1', 'expire', 100))
    assert ledger.balance(conn, 'C-1') == 0
    ledger.record(conn, Event('C-1', 'adjust', -5, note='test'))
    assert ledger.balance(conn, 'C-1') == 0


def test_refund_takes_back_the_orders_points(conn):
    ledger.record(conn, Event('C-1', 'earn', 300, order_id='SO-7'))
    ledger.record(conn, Event('C-1', 'refund', order_id='SO-7'))
    assert ledger.balance(conn, 'C-1') == 0
    *_, last = ledger.history(conn, 'C-1')
    assert last[1:4] == ('refund', 300, 'SO-7')


def test_an_order_is_refunded_once(conn):
    ledger.record(conn, Event('C-1', 'earn', 300, order_id='SO-7'))
    ledger.record(conn, Event('C-1', 'refund', order_id='SO-7'))
    with pytest.raises(LedgerError):
        ledger.record(conn, Event('C-1', 'refund', order_id='SO-7'))


def test_refund_needs_an_order_that_earned_points(conn):
    with pytest.raises(LedgerError):
        ledger.record(conn, Event('C-1', 'refund', order_id='SO-404'))


def test_unknown_customers_and_kinds_are_rejected(conn):
    with pytest.raises(LedgerError):
        ledger.record(conn, Event('C-9', 'earn', 10, order_id='SO-1'))
    with pytest.raises(LedgerError):
        ledger.record(conn, Event('C-1', 'gift', 10))
