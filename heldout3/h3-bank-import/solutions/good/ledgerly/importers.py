"""LED-12: reading bank statements (ISSUES/LED-12.md)."""

import csv
import datetime as dt
import io
import re
from collections import Counter
from decimal import Decimal, InvalidOperation

from ledgerly import rules, store
from ledgerly.models import Transaction

NORDBANK = ['Buchungstag', 'Valuta', 'Verwendungszweck', 'Betrag', 'Währung']
WESTPAY = ['Date', 'Description', 'Debit', 'Credit', 'Balance']


class UnknownFormat(Exception):
    pass


class BadRow(Exception):
    def __init__(self, line, problem):
        super().__init__(f'line {line}: {problem}')
        self.line, self.problem = line, problem


def clean(description):
    return re.sub(r'\s+', ' ', description).strip()


def german_amount(text):
    if not re.fullmatch(r'-?\d{1,3}(\.\d{3})*,\d{2}|-?\d+,\d{2}', text.strip()):
        raise ValueError(f'not an amount: {text!r}')
    return Decimal(text.strip().replace('.', '').replace(',', '.'))


def plain_amount(text):
    if not re.fullmatch(r'\d+(\.\d{1,2})?', text.strip()):
        raise ValueError(f'not an amount: {text!r}')
    return Decimal(text.strip())


def nordbank(rows):
    for line, row in rows:
        try:
            date = dt.datetime.strptime(row['Buchungstag'], '%d.%m.%Y').date()
        except ValueError:
            raise BadRow(line, f"not a date: {row['Buchungstag']!r}") from None
        try:
            amount = german_amount(row['Betrag'])
        except ValueError as error:
            raise BadRow(line, str(error)) from None
        if row['Währung'].strip() != 'EUR':
            raise BadRow(line, f"not in EUR: {row['Währung']!r}")
        yield date, amount, clean(row['Verwendungszweck'])


def westpay(rows):
    for line, row in rows:
        try:
            date = dt.date.fromisoformat(row['Date'].strip())
        except ValueError:
            raise BadRow(line, f"not a date: {row['Date']!r}") from None
        debit, credit = row['Debit'].strip(), row['Credit'].strip()
        if bool(debit) == bool(credit):
            raise BadRow(line, 'needs exactly one of Debit and Credit')
        try:
            amount = plain_amount(credit) if credit else -plain_amount(debit)
        except ValueError as error:
            raise BadRow(line, str(error)) from None
        yield date, amount, clean(row['Description'])


def read(path):
    """[(date, amount, description)] from a statement, in file order."""
    with open(path, encoding='utf-8-sig', newline='') as handle:
        text = handle.read()
    first = text.splitlines()[0] if text else ''
    if first.split(';') == NORDBANK:
        reader, parse = csv.reader(io.StringIO(text), delimiter=';'), nordbank
    elif next(csv.reader([first]), []) == WESTPAY:
        reader, parse = csv.reader(io.StringIO(text)), westpay
    else:
        raise UnknownFormat(path)
    header = next(reader)
    rows = []
    for line, values in enumerate(reader, 2):
        if not values:
            continue
        if len(values) != len(header):
            raise BadRow(line, f'expected {len(header)} fields, found {len(values)}')
        rows.append((line, dict(zip(header, values))))
    return list(parse(rows))


def import_statement(path, account):
    """Adds the statement's new transactions to the ledger. Returns (imported, skipped)."""
    entries = read(path)
    already = Counter((t.account, t.date, t.amount, t.description) for t in store.load())
    found = rules.load()
    new, skipped = [], 0
    for date, amount, description in entries:
        key = (account, date, amount.quantize(Decimal('0.01')), description)
        if already[key] > 0:
            already[key] -= 1
            skipped += 1
            continue
        new.append(Transaction(date, amount, description, account, rules.categorize(description, found)))
    store.append(new)
    return len(new), skipped
