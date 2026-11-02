"""Customers and invoices, as the billing system exports them to data/invoices.json."""

import dataclasses
import datetime as dt
import json
import os
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

# The nightly export from billing; INVOICING_DATA points somewhere else (the tests use it).
DEFAULT_PATH = Path(__file__).resolve().parent.parent / 'data' / 'invoices.json'
CENT = Decimal('0.01')


@dataclasses.dataclass(frozen=True)
class Customer:
    id: str
    name: str
    timezone: str  # IANA name, e.g. America/New_York
    terms: str  # payment terms, see terms.py


@dataclasses.dataclass(frozen=True)
class Line:
    description: str
    quantity: int
    unit_price: Decimal

    @property
    def total(self):
        return (self.unit_price * self.quantity).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclasses.dataclass(frozen=True)
class Invoice:
    number: str
    customer: Customer
    issued_at: dt.datetime  # when billing issued it, in UTC
    lines: tuple = ()

    @property
    def total(self):
        return sum((line.total for line in self.lines), Decimal('0.00'))


def parse_time(text):
    """Billing's timestamps: UTC, like 2026-09-30T14:05:00Z."""
    return dt.datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)


def data_path():
    return Path(os.environ.get('INVOICING_DATA') or DEFAULT_PATH)


def load(path=None):
    """{number: Invoice} from billing's export."""
    data = json.loads(Path(path or data_path()).read_text(encoding='utf-8'))
    customers = {c['id']: Customer(c['id'], c['name'], c['timezone'], c['terms']) for c in data['customers']}
    invoices = {}
    for item in data['invoices']:
        customer = customers[item['customer']]
        # Kept in UTC: render.py shows it in the customer's timezone (BILL-388).
        issued = parse_time(item['issued_at'])
        lines = tuple(Line(line['description'], line['quantity'], Decimal(line['unit_price']))
                      for line in item['lines'])
        invoices[item['number']] = Invoice(item['number'], customer, issued, lines)
    return invoices
