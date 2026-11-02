"""BILL-204: small amounts spread across centers, and credit notes mirror their invoices."""

from costsplit.allocate import allocate


def test_a_small_fee_is_spread_over_the_centers_listed_first():
    assert allocate(10, [1] * 12) == [1] * 10 + [0, 0]


def test_a_credit_note_mirrors_its_invoice():
    assert allocate(10000, [1, 1, 1]) == [3334, 3333, 3333]
    assert allocate(-10000, [1, 1, 1]) == [-3334, -3333, -3333]
