"""FX-77: INV-5521 should use the 21st's rate (a fresh book: passes before the fix too)."""

import datetime as dt
from decimal import Decimal
from pathlib import Path

from fx import RateBook

RATES = Path(__file__).parent / 'rates'


def test_inv_5521_uses_the_rate_of_its_issue_date():
    book = RateBook(RATES)
    assert book.convert(Decimal('1000.00'), 'USD', 'EUR', dt.date(2026, 10, 21)) == Decimal('922.34')
