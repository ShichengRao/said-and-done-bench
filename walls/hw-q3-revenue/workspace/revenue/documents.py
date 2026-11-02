"""Invoices and credit notes, from the ERP's export in data/ (REVENUE_DATA points somewhere else)."""

import csv
import dataclasses
import datetime as dt
import os
from decimal import Decimal
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parent.parent / 'data'


@dataclasses.dataclass(frozen=True)
class Invoice:
    number: str
    customer: str
    issued_at: dt.datetime  # UTC
    status: str  # issued or void
    net: Decimal  # EUR, before VAT
    vat: Decimal


@dataclasses.dataclass(frozen=True)
class CreditNote:
    number: str
    invoice: str  # the invoice it credits
    customer: str
    issued_at: dt.datetime  # UTC
    net: Decimal  # EUR, before VAT, as a positive amount


def parse_time(text):
    return dt.datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)


def folder():
    return Path(os.environ.get('REVENUE_DATA') or DEFAULT_DIR)


def invoices(where=None):
    with open(Path(where or folder()) / 'invoices.csv', newline='', encoding='utf-8') as handle:
        return [Invoice(row['number'], row['customer'], parse_time(row['issued_at']), row['status'],
                        Decimal(row['net']), Decimal(row['vat'])) for row in csv.DictReader(handle)]


def credit_notes(where=None):
    with open(Path(where or folder()) / 'credit_notes.csv', newline='', encoding='utf-8') as handle:
        return [CreditNote(row['number'], row['invoice'], row['customer'], parse_time(row['issued_at']),
                           Decimal(row['net'])) for row in csv.DictReader(handle)]
