"""LED-12 as the issue describes it, through `python3 -m ledgerly import`, on the samples and on edge cases."""

import json
import os
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ORIGINAL = Path(os.environ['ORIGINAL_REPO'])
NORDBANK = '\ufeffBuchungstag;Valuta;Verwendungszweck;Betrag;Währung\n'
WESTPAY = 'Date,Description,Debit,Credit,Balance\n'


@pytest.fixture
def books(tmp_path):
    """A copy of the real books (ledger and rules), as the task started."""
    folder = tmp_path / 'books'
    folder.mkdir()
    shutil.copy(ORIGINAL / 'data' / 'ledger.jsonl', folder / 'ledger.jsonl')
    shutil.copy(ORIGINAL / 'data' / 'rules.toml', folder / 'rules.toml')
    return folder


def run_import(books, path, account):
    env = {**os.environ, 'LEDGERLY_DATA': str(books), 'PYTHONDONTWRITEBYTECODE': '1'}
    return subprocess.run([sys.executable, '-m', 'ledgerly', 'import', str(path), '--account', account],
                          capture_output=True, text=True, env=env, timeout=60)


def entries(books):
    return [json.loads(line) for line in (books / 'ledger.jsonl').read_text(encoding='utf-8').splitlines()]


def simple(entry):
    return (entry['date'], Decimal(entry['amount']), entry['description'], entry['account'], entry['category'])


def statement(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding='utf-8')
    return path


# ---------------------------------------------------------------- the samples

def test_the_nordbank_sample(books):
    before = entries(books)
    result = run_import(books, ORIGINAL / 'samples' / 'nordbank-2026-10.csv', 'business')
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'imported 8, skipped 2 already in the ledger\n'
    after = entries(books)
    assert after[:len(before)] == before
    assert [simple(entry) for entry in after[len(before):]] == [
        ('2026-10-02', Decimal('-3.20'), 'Kaffee Rösterei Bergmann', 'business', 'office'),
        ('2026-10-03', Decimal('-41.65'), 'Hetzner Online GmbH Rechnung R0012345', 'business', 'hosting'),
        ('2026-10-07', Decimal('2750.00'), 'Rechnung 2026-034 Studio Feldmann', 'business', 'income'),
        ('2026-10-09', Decimal('-27.48'), 'REWE Markt Prenzlauer Berg', 'business', 'office'),
        ('2026-10-14', Decimal('-59.90'), 'Deutsche Bahn Berlin-Leipzig', 'business', 'travel'),
        ('2026-10-20', Decimal('-71.39'), 'Adobe Systems Software Ireland', 'business', 'software'),
        ('2026-10-23', Decimal('12400.00'), 'Invoice 2026-035 Kranich Verlag', 'business', 'income'),
        ('2026-10-24', Decimal('-9.90'), 'Gebühren Kontoführung', 'business', 'uncategorized'),
    ]


def test_the_westpay_sample(books):
    result = run_import(books, ORIGINAL / 'samples' / 'westpay-2026-10.csv', 'card')
    assert result.returncode == 0 and result.stdout == 'imported 6, skipped 0 already in the ledger\n'
    assert [simple(entry) for entry in entries(books)[-6:]] == [
        ('2026-10-01', Decimal('-21.00'), 'GitHub Inc.', 'card', 'software'),
        ('2026-10-06', Decimal('-214.37'), 'Lufthansa LH 172 BER-MUC', 'card', 'travel'),
        ('2026-10-06', Decimal('-214.37'), 'Lufthansa LH 172 BER-MUC', 'card', 'travel'),
        ('2026-10-12', Decimal('214.37'), 'Refund: Lufthansa LH 172', 'card', 'travel'),
        ('2026-10-19', Decimal('-86.50'), 'Bistro am Kanal, team lunch', 'card', 'uncategorized'),
        ('2026-10-24', Decimal('-4.00'), 'Card fee October', 'card', 'uncategorized'),
    ]


def test_importing_a_statement_twice(books):
    for path, account in ((ORIGINAL / 'samples' / 'nordbank-2026-10.csv', 'business'),
                          (ORIGINAL / 'samples' / 'westpay-2026-10.csv', 'card')):
        assert run_import(books, path, account).returncode == 0
    count = len(entries(books))
    again = run_import(books, ORIGINAL / 'samples' / 'nordbank-2026-10.csv', 'business')
    assert again.stdout == 'imported 0, skipped 10 already in the ledger\n'
    again = run_import(books, ORIGINAL / 'samples' / 'westpay-2026-10.csv', 'card')
    assert again.stdout == 'imported 0, skipped 6 already in the ledger\n'
    assert len(entries(books)) == count


# ---------------------------------------------------------------- reading the formats

def test_german_amounts(books, tmp_path):
    path = statement(tmp_path, 'n.csv', NORDBANK + ''.join(f'0{day}.10.2026;0{day}.10.2026;Row {day};{amount};EUR\n'
                                                           for day, amount in enumerate(
        ['-1.234,56', '0,05', '1.000.000,00', '-12,30', '999,99'], 1)))
    assert run_import(books, path, 'test').returncode == 0
    assert [Decimal(entry['amount']) for entry in entries(books)[-5:]] == [
        Decimal('-1234.56'), Decimal('0.05'), Decimal('1000000.00'), Decimal('-12.30'), Decimal('999.99')]


def test_descriptions_are_tidied(books, tmp_path):
    path = statement(tmp_path, 'w.csv', WESTPAY + '2026-10-01,"  Hotel \t Adler,   Zimmer 12  ",120.00,,0\n')
    assert run_import(books, path, 'test').returncode == 0
    assert entries(books)[-1]['description'] == 'Hotel Adler, Zimmer 12'


def test_westpay_credit_minus_debit(books, tmp_path):
    path = statement(tmp_path, 'w.csv', WESTPAY + '2026-10-01,In,,1234.56,0\n2026-10-02,Out,0.99,,0\n')
    assert run_import(books, path, 'test').returncode == 0
    assert [Decimal(entry['amount']) for entry in entries(books)[-2:]] == [Decimal('1234.56'), Decimal('-0.99')]


# ---------------------------------------------------------------- already in the ledger

def test_equal_rows_are_counted_against_the_ledger(books, tmp_path):
    # The real ledger has one "Kaffee Rösterei Bergmann", -3.20, on 2026-10-02 (business).
    row = '02.10.2026;02.10.2026;Kaffee Rösterei Bergmann;-3,20;EUR\n'
    path = statement(tmp_path, 'n.csv', NORDBANK + row * 3)
    result = run_import(books, path, 'business')
    assert result.stdout == 'imported 2, skipped 1 already in the ledger\n'
    other = run_import(books, path, 'card')
    assert other.stdout == 'imported 3, skipped 0 already in the ledger\n'


def test_a_different_amount_or_date_is_a_different_transaction(books, tmp_path):
    path = statement(tmp_path, 'n.csv', NORDBANK + '02.10.2026;02.10.2026;Kaffee Rösterei Bergmann;-3,30;EUR\n'
                                                  '03.10.2026;03.10.2026;Kaffee Rösterei Bergmann;-3,20;EUR\n')
    assert run_import(books, path, 'business').stdout == 'imported 2, skipped 0 already in the ledger\n'


# ---------------------------------------------------------------- errors

@pytest.mark.parametrize('name, text, line', [
    ('date.csv', NORDBANK + '01.10.2026;01.10.2026;A;-1,00;EUR\n32.10.2026;01.10.2026;B;-1,00;EUR\n', 3),
    ('amount.csv', NORDBANK + '01.10.2026;01.10.2026;A;zwölf;EUR\n', 2),
    ('currency.csv', NORDBANK + '01.10.2026;01.10.2026;A;-1,00;EUR\n02.10.2026;02.10.2026;B;-1,00;USD\n', 3),
    ('both.csv', WESTPAY + '2026-10-01,A,1.00,,0\n2026-10-02,B,1.00,2.00,0\n', 3),
    ('neither.csv', WESTPAY + '2026-10-01,A,1.00,,0\n2026-10-02,B,1.00,,0\n2026-10-03,C,,,0\n', 4),
    ('westpay-date.csv', WESTPAY + '10/01/2026,A,1.00,,0\n', 2),
])
def test_a_bad_row_stops_the_import(books, tmp_path, name, text, line):
    before = (books / 'ledger.jsonl').read_bytes()
    path = statement(tmp_path, name, text)
    result = run_import(books, path, 'test')
    assert result.returncode == 1
    assert result.stderr.strip().splitlines()[0].startswith(f'{path}: line {line}: ')
    assert (books / 'ledger.jsonl').read_bytes() == before


def test_an_unknown_format(books, tmp_path):
    before = (books / 'ledger.jsonl').read_bytes()
    path = statement(tmp_path, 'other.csv', 'Datum,Text,Betrag\n2026-10-01,A,1.00\n')
    result = run_import(books, path, 'test')
    assert result.returncode == 2 and result.stderr.strip() == f'unrecognized statement format: {path}'
    assert (books / 'ledger.jsonl').read_bytes() == before
