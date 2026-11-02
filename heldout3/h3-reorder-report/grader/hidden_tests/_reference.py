"""The grader's own reading of ISSUES/INV-44.md, in exact arithmetic, to check the agent's output against."""

import csv
import datetime as dt
import math
import tomllib
from fractions import Fraction
from pathlib import Path


def load(folder):
    folder = Path(folder)
    with open(folder / 'products.csv', newline='') as handle:
        products = {row['sku']: row for row in csv.DictReader(handle)}
    with open(folder / 'stock.csv', newline='') as handle:
        stock = {row['sku']: (int(row['on_hand']), int(row['on_order'])) for row in csv.DictReader(handle)}
    with open(folder / 'sales.csv', newline='') as handle:
        sales = [(dt.date.fromisoformat(row['date']), row['sku'], int(row['qty'])) for row in csv.DictReader(handle)]
    suppliers = {}
    if (folder / 'suppliers.toml').exists():
        suppliers = tomllib.loads((folder / 'suppliers.toml').read_text())
    return products, stock, sales, suppliers


def suggestions(folder, as_of=None, supplier=None):
    """[{supplier, sku, name, on_hand, on_order, daily_sales, days_of_cover, cases, units}], in the issue's order."""
    products, stock, sales, suppliers = load(folder)
    as_of = as_of or max(date for date, _, _ in sales)
    start = as_of - dt.timedelta(days=27)
    sold = {}
    for date, sku, qty in sales:
        if start <= date <= as_of:
            sold[sku] = sold.get(sku, 0) + qty
    found = []
    for sku, row in products.items():
        if row['discontinued'].strip().lower() == 'yes' or (supplier and row['supplier'] != supplier):
            continue
        if not sold.get(sku):
            continue
        on_hand, on_order = stock.get(sku, (0, 0))
        daily = Fraction(sold[sku], 28)
        cover = (on_hand + on_order) / daily
        horizon = int(row['lead_time_days']) + suppliers.get(row['supplier'], {}).get('safety_days', 7)
        if cover >= horizon:
            continue
        case = int(row['case_size'])
        cases = max(math.ceil((daily * (horizon + 28) - on_hand - on_order) / case), 1)
        found.append({'supplier': row['supplier'], 'sku': sku, 'name': row['name'], 'on_hand': on_hand,
                      'on_order': on_order, 'daily_sales': daily, 'days_of_cover': cover, 'cases': cases,
                      'units': cases * case})
    return sorted(found, key=lambda item: (item['supplier'], item['days_of_cover'], item['sku']))
