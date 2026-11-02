from decimal import Decimal

import pytest

from fernbill.rates import RateTable


def test_base_rate_is_one(rates):
    assert rates.rate("USD") == Decimal(1)


def test_convert_usd_to_eur(rates):
    assert rates.convert(Decimal("100.00"), "USD", "EUR") == Decimal("92.13")


def test_convert_usd_to_jpy(rates):
    assert rates.convert(Decimal("12.34"), "USD", "JPY") == Decimal("1849")


def test_convert_usd_to_bhd(rates):
    assert rates.convert(Decimal("19.99"), "USD", "BHD") == Decimal("7.536")


def test_convert_eur_to_gbp(rates):
    assert rates.convert(Decimal("50.00"), "EUR", "GBP") == Decimal("42.55")


def test_unknown_currency(rates):
    with pytest.raises(KeyError):
        rates.convert(Decimal("1.00"), "USD", "XYZ")


def test_repr_names_the_snapshot(rates):
    assert "base='USD', date='2026-10-01'" in repr(rates)


def test_rejects_non_positive_rates():
    with pytest.raises(ValueError):
        RateTable.from_snapshot({"base": "USD", "currencies": {"EUR": {"rate": "0"}}})


def test_convert_usd_to_lyd_uses_the_snapshot_units(rates):
    # LYD has three decimal places, and the ISO table in fernbill/currency.py doesn't list it.
    assert rates.convert(Decimal("12.34"), "USD", "LYD") == Decimal("66.895")
