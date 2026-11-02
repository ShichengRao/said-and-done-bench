"""Conversions the visible tests don't cover: other zero-decimal currencies, currencies
only the snapshot knows (XAF, CLF), and three- and four-decimal ones.

A fix that special-cases JPY, or that goes back to the ISO table and ignores the
snapshot, gets some of these wrong. Results must also be quantized to exactly the
minor unit: Decimal('1849.00') equals Decimal('1849') but isn't rounded to yen.
"""

from decimal import Decimal

import pytest

from fernbill.invoice import Invoice, LineItem
from fernbill.rates import RateTable

SNAPSHOT = {
    "base": "USD",
    "date": "2026-10-20",
    "currencies": {
        "BHD": {"rate": "0.3770", "minor_units": 3},
        "CLF": {"rate": "0.024567", "minor_units": 4},
        "EUR": {"rate": "0.9213", "minor_units": 2},
        "GBP": {"rate": "0.7841"},
        "ISK": {"rate": "137.90", "minor_units": 0},
        "JPY": {"rate": "149.82", "minor_units": 0},
        "KRW": {"rate": "1371.5", "minor_units": 0},
        "LYD": {"rate": "5.4210", "minor_units": 3},
        "TND": {"rate": "3.0815", "minor_units": 3},
        "VND": {"rate": "25340", "minor_units": 0},
        "XAF": {"rate": "604.37", "minor_units": 0},
    },
}


@pytest.fixture
def table():
    return RateTable.from_snapshot(SNAPSHOT)


def same(result, expected):
    expected = Decimal(expected)
    return result == expected and result.as_tuple().exponent == expected.as_tuple().exponent


@pytest.mark.parametrize(("code", "places"), [
    ("JPY", 0), ("KRW", 0), ("ISK", 0), ("VND", 0), ("XAF", 0),
    ("BHD", 3), ("LYD", 3), ("TND", 3), ("CLF", 4), ("EUR", 2), ("GBP", 2), ("USD", 2),
])
def test_minor_units(table, code, places):
    assert table.minor_units(code) == places


@pytest.mark.parametrize(("code", "expected"), [
    ("JPY", "1849"), ("KRW", "16924"), ("ISK", "1702"), ("VND", "312696"), ("XAF", "7458"),
    ("BHD", "4.652"), ("LYD", "66.895"), ("TND", "38.026"), ("CLF", "0.3032"),
    ("EUR", "11.37"), ("GBP", "9.68"),
])
def test_convert_from_usd(table, code, expected):
    result = table.convert(Decimal("12.34"), "USD", code)
    assert same(result, expected), result


def test_convert_between_two_non_base_currencies(table):
    assert same(table.convert(Decimal("50.00"), "EUR", "KRW"), "74433")


def consulting():
    return Invoice("USD", [
        LineItem("Consulting", Decimal("3"), Decimal("120.00"), Decimal("0.0825")),
        LineItem("Hosting", Decimal("1"), Decimal("49.99"), Decimal("0.0825")),
        LineItem("Setup fee", Decimal("1"), Decimal("15.00")),
    ])


@pytest.mark.parametrize(("code", "expected"), [
    ("KRW", "629259"), ("XAF", "277291"), ("JPY", "68739"), ("TND", "1413.824"), ("EUR", "422.70"),
])
def test_invoice_total_in(table, code, expected):
    assert same(consulting().total_in(code, table), expected)

