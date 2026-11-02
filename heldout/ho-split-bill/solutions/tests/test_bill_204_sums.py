"""BILL-204, checked only by totals (these pass on the old code too)."""

from costsplit.allocate import allocate


def test_a_credit_note_adds_up():
    assert sum(allocate(-10000, [1, 1, 1])) == -10000


def test_the_fee_adds_up():
    assert sum(allocate(10, [1] * 12)) == 10
