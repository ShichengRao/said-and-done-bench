"""FX-77: a long-lived book has to follow the day it's asked about."""

import datetime as dt
from decimal import Decimal
from pathlib import Path

from fx import RateBook

RATES = Path(__file__).parent / 'rates'


def test_a_book_uses_each_days_rates_as_the_days_go_by():
    book = RateBook(RATES)
    assert book.rate('USD', dt.date(2026, 10, 20)) == Decimal('1.0791')
    assert book.convert(Decimal('1000.00'), 'USD', 'EUR', dt.date(2026, 10, 21)) == Decimal('922.34')
