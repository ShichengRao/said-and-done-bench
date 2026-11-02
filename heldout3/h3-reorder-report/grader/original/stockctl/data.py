"""The warehouse's data: products, stock levels, daily sales, and suppliers.

STOCKCTL_DATA names the folder (default: data/ in the repository):

    products.csv   sku, name, supplier, case_size, lead_time_days, discontinued (yes/no)
    stock.csv      sku, on_hand, on_order (units)
    sales.csv      date, sku, qty: units sold that day (days without sales have no row)
    suppliers.toml one table per supplier, e.g. [halden] safety_days = 10
"""

import csv
import datetime as dt
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_FOLDER = Path(__file__).resolve().parent.parent / 'data'


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    supplier: str
    case_size: int
    lead_time_days: int
    discontinued: bool


@dataclass(frozen=True)
class Stock:
    on_hand: int
    on_order: int


@dataclass(frozen=True)
class Sale:
    date: dt.date
    sku: str
    qty: int


def folder():
    return Path(os.environ.get('STOCKCTL_DATA') or DEFAULT_FOLDER)


def _rows(name):
    with open(folder() / name, newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def products():
    """{sku: Product}"""
    return {row['sku']: Product(row['sku'], row['name'], row['supplier'], int(row['case_size']),
                                int(row['lead_time_days']), row['discontinued'].strip().lower() == 'yes')
            for row in _rows('products.csv')}


def stock():
    """{sku: Stock}; a product with no row has nothing on hand or on order."""
    return {row['sku']: Stock(int(row['on_hand']), int(row['on_order'])) for row in _rows('stock.csv')}


def sales():
    return [Sale(dt.date.fromisoformat(row['date']), row['sku'], int(row['qty'])) for row in _rows('sales.csv')]


def suppliers():
    """{supplier: {setting: value}}"""
    path = folder() / 'suppliers.toml'
    if not path.exists():
        return {}
    with open(path, 'rb') as handle:
        return tomllib.load(handle)
