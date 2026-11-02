"""FX-77 in a long-lived book: days moving on, weekends, and files that arrive while it's open."""

import datetime as dt
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from fx import NoRates, RateBook

FIXTURES = Path(__file__).parent / 'rates'


@pytest.fixture
def folder(tmp_path):
    for path in FIXTURES.glob('*.json'):
        shutil.copy(path, tmp_path / path.name)
    return tmp_path


def add_file(folder, day, usd):
    (folder / f'{day}.json').write_text(json.dumps({'base': 'EUR', 'date': day, 'rates': {'USD': usd}}))


def test_each_day_in_turn(folder):
    book = RateBook(folder)
    days = [(15, '1.0768'), (16, '1.0773'), (17, '1.0773'), (18, '1.0773'), (19, '1.0785'), (20, '1.0791'),
            (21, '1.0842'), (22, '1.0842')]
    assert [book.rate('USD', dt.date(2026, 10, day)) for day, _ in days] == [Decimal(rate) for _, rate in days]


def test_going_back_a_day(folder):
    book = RateBook(folder)
    assert book.rate('USD', dt.date(2026, 10, 21)) == Decimal('1.0842')
    assert book.rate('USD', dt.date(2026, 10, 20)) == Decimal('1.0791')
    assert book.rate('USD', dt.date(2026, 10, 21)) == Decimal('1.0842')


def test_a_file_written_while_the_book_is_open(folder):
    book = RateBook(folder)
    assert book.rate('USD', dt.date(2026, 10, 21)) == Decimal('1.0842')
    add_file(folder, '2026-10-22', '1.0866')
    assert book.rate('USD', dt.date(2026, 10, 22)) == Decimal('1.0866')


def test_a_day_looked_up_before_its_file_arrives(folder):
    book = RateBook(folder)
    assert book.rate('USD', dt.date(2026, 10, 22)) == Decimal('1.0842')  # 00:02: no file for the 22nd yet
    add_file(folder, '2026-10-22', '1.0866')  # 00:05: the rates job
    assert book.rate('USD', dt.date(2026, 10, 22)) == Decimal('1.0866')  # 00:12


def test_interleaved_currencies_and_days(folder):
    book = RateBook(folder)
    assert book.convert(Decimal('100'), 'GBP', 'USD', dt.date(2026, 10, 16)) == Decimal('125.25')
    assert book.convert(Decimal('100'), 'GBP', 'USD', dt.date(2026, 10, 21)) == Decimal('125.49')
    assert book.convert(Decimal('100'), 'JPY', 'EUR', dt.date(2026, 10, 19)) == Decimal('0.62')


def test_no_rates_before_the_first_file_even_after_later_lookups(folder):
    book = RateBook(folder)
    book.rate('USD', dt.date(2026, 10, 21))
    with pytest.raises(NoRates):
        book.rate('USD', dt.date(2026, 10, 14))
