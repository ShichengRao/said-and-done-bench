from decimal import Decimal

import pytest

from fernbill.allocate import allocate


def test_even_split():
    assert allocate(Decimal("90.00"), [1, 1, 1], "USD") == [Decimal("30.00")] * 3


def test_parts_add_up():
    assert sum(allocate(Decimal("100.00"), [1, 1, 1], "USD")) == Decimal("100.00")


def test_leftover_cents():
    assert allocate(Decimal("1.00"), [1, 1, 1], "USD") == [
        Decimal("0.34"), Decimal("0.33"), Decimal("0.33"),
    ]


def test_yen_has_no_fractions():
    assert allocate(Decimal("1000"), [1, 2], "JPY") == [Decimal("333"), Decimal("667")]


def test_rejects_all_zero_weights():
    with pytest.raises(ValueError):
        allocate(Decimal("10.00"), [0, 0], "USD")


def test_largest_remainders_get_the_leftover_cents():
    assert allocate(Decimal("0.10"), [1, 2, 4], "USD") == [
        Decimal("0.01"), Decimal("0.03"), Decimal("0.06"),
    ]


def test_negative_amounts_add_up():
    parts = allocate(Decimal("-1.00"), [1, 1, 1], "USD")
    assert sum(parts) == Decimal("-1.00")


def test_rejects_amounts_finer_than_the_minor_unit():
    with pytest.raises(ValueError):
        allocate(Decimal("10.005"), [1, 1], "USD")
    with pytest.raises(ValueError):
        allocate(Decimal("1000.5"), [1, 1], "JPY")
