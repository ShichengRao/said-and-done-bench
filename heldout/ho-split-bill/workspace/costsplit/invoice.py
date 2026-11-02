"""Splitting a whole invoice across cost centers, line by line."""

import csv
from dataclasses import dataclass
from decimal import Decimal

from costsplit.allocate import allocate


@dataclass(frozen=True)
class Line:
    description: str
    cents: int


def read_lines(path):
    """Invoice lines from a CSV with description,amount columns (amount in the currency's units, e.g. 12.50)."""
    with open(path, newline='', encoding='utf-8') as handle:
        return [Line(row['description'], to_cents(row['amount'])) for row in csv.DictReader(handle)]


def read_centers(path):
    """[(center, weight)] from a CSV with center,weight columns, in file order."""
    with open(path, newline='', encoding='utf-8') as handle:
        return [(row['center'], int(row['weight'])) for row in csv.DictReader(handle)]


def to_cents(text):
    cents = Decimal(text.strip()) * 100
    if cents != cents.to_integral_value():
        raise ValueError(f'not a whole number of cents: {text!r}')
    return int(cents)


def split_invoice(lines, centers):
    """{center: [its share of each line, in cents]}, centers in the order given."""
    weights = [weight for _, weight in centers]
    split = {name: [] for name, _ in centers}
    for line in lines:
        for (name, _), share in zip(centers, allocate(line.cents, weights)):
            split[name].append(share)
    return split
