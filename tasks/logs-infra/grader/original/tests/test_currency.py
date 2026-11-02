from decimal import Decimal

import pytest

from fernbill.currency import check_code, minor_units, quantize, round_to


def test_most_currencies_have_two_decimals():
    assert minor_units("USD") == 2
    assert minor_units("EUR") == 2


def test_zero_decimal_currencies():
    assert minor_units("JPY") == 0
    assert minor_units("KRW") == 0


def test_three_decimal_currencies():
    assert minor_units("KWD") == 3
    assert minor_units("BHD") == 3


def test_quantize_rounds_half_up():
    assert quantize(Decimal("0.125"), 2) == Decimal("0.13")
    assert quantize(Decimal("2.5"), 0) == Decimal("3")


def test_quantize_rounds_negative_amounts_away_from_zero():
    assert quantize(Decimal("-0.125"), 2) == Decimal("-0.13")


def test_round_to_currency():
    assert round_to(Decimal("1848.7788"), "JPY") == Decimal("1849")
    assert round_to(Decimal("7.53623"), "BHD") == Decimal("7.536")


def test_round_to_keeps_trailing_zeros():
    assert str(round_to(Decimal("5"), "USD")) == "5.00"


def test_check_code_accepts_iso_codes():
    assert check_code("EUR") == "EUR"


def test_check_code_rejects_anything_else():
    for bad in ("eur", "EURO", "E1R", "", None):
        with pytest.raises(ValueError):
            check_code(bad)
