import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from fx import NoRates, RateBook, UnknownCurrency

RATES = Path(__file__).parent / 'rates'


@pytest.fixture
def book():
    return RateBook(RATES)


def test_rate_on_a_business_day(book):
    assert book.rate('USD', dt.date(2026, 10, 20)) == Decimal('1.0791')


def test_a_weekend_uses_fridays_rates(book):
    assert book.rate('GBP', dt.date(2026, 10, 18)) == Decimal('0.8601')


def test_euro_is_one(book):
    assert book.rate('EUR', dt.date(2026, 10, 16)) == 1


def test_unknown_currency(book):
    with pytest.raises(UnknownCurrency):
        book.rate('XYZ', dt.date(2026, 10, 16))


def test_no_rates_before_the_first_file(book):
    with pytest.raises(NoRates):
        book.rate('USD', dt.date(2026, 10, 14))


def test_convert_to_euros(book):
    assert book.convert(Decimal('1000.00'), 'USD', 'EUR', dt.date(2026, 10, 19)) == Decimal('927.21')


def test_convert_between_two_other_currencies(book):
    assert book.convert(Decimal('250.00'), 'GBP', 'CHF', dt.date(2026, 10, 15)) == Decimal('273.50')
