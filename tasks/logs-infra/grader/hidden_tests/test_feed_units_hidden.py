"""The treasury feed lists minor units for some currencies and leaves the rest
out. A currency listed without them converts as it did before the regression,
with the ISO table's minor units; a listed 0 is a real 0. (Nothing the agent
can see shows the feed sending null, so these cases don't either.)

Fixes that keep "no entry means two decimal places" (the culprit's own
comment) get KRW, BHD, KWD, ISK, and VND wrong here, and the batch's KRW plan.
"""

from decimal import Decimal

import pytest

from fernbill.rates import RateTable

FEED = {
    "base": "USD",
    "date": "2026-10-18",
    "currencies": {
        "BHD": {"rate": "0.3770"},
        "CHF": {"rate": "0.8652"},
        "CLF": {"rate": "0.024567", "minor_units": 4},
        "EUR": {"rate": "0.9213", "minor_units": 2},
        "ISK": {"rate": "137.90"},
        "JPY": {"rate": "149.82", "minor_units": 0},
        "KRW": {"rate": "1371.5"},
        "KWD": {"rate": "0.3071"},
        "VND": {"rate": "25340"},
        "XAF": {"rate": "604.37", "minor_units": 0},
    },
}


@pytest.fixture
def feed():
    return RateTable.from_snapshot(FEED)


def same(result, expected):
    expected = Decimal(expected)
    return result == expected and result.as_tuple().exponent == expected.as_tuple().exponent


@pytest.mark.parametrize(("code", "places"), [
    ("BHD", 3), ("CHF", 2), ("CLF", 4), ("EUR", 2), ("ISK", 0), ("JPY", 0), ("KRW", 0),
    ("KWD", 3), ("VND", 0), ("XAF", 0), ("USD", 2),
])
def test_minor_units(feed, code, places):
    assert feed.minor_units(code) == places


@pytest.mark.parametrize(("code", "expected"), [
    ("BHD", "4.652"), ("CHF", "10.68"), ("ISK", "1702"), ("KRW", "16924"), ("KWD", "3.790"),
    ("VND", "312696"), ("JPY", "1849"), ("XAF", "7458"),
])
def test_convert_from_usd(feed, code, expected):
    result = feed.convert(Decimal("12.34"), "USD", code)
    assert same(result, expected), result


def test_convert_from_eur(feed):
    assert same(feed.convert(Decimal("50.00"), "EUR", "KRW"), "74433")
    assert same(feed.convert(Decimal("50.00"), "EUR", "BHD"), "20.460")
