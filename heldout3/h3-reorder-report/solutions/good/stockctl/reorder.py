"""INV-44: what to reorder from each supplier (ISSUES/INV-44.md)."""

import datetime as dt
import math
from dataclasses import dataclass
from fractions import Fraction

from stockctl import data

WINDOW_DAYS = 28
REVIEW_DAYS = 28
DEFAULT_SAFETY_DAYS = 7


@dataclass(frozen=True)
class Suggestion:
    product: data.Product
    on_hand: int
    on_order: int
    daily_sales: Fraction
    days_of_cover: Fraction
    cases: int

    @property
    def units(self):
        return self.cases * self.product.case_size


def suggestions(products, stock, sales, suppliers, as_of=None, supplier=None):
    """The products to reorder, by supplier, then days of cover, then SKU."""
    if as_of is None:
        as_of = max(sale.date for sale in sales)
    start = as_of - dt.timedelta(days=WINDOW_DAYS - 1)
    sold = {}
    for sale in sales:
        if start <= sale.date <= as_of:
            sold[sale.sku] = sold.get(sale.sku, 0) + sale.qty
    found = []
    for product in products.values():
        if product.discontinued or (supplier and product.supplier != supplier) or not sold.get(product.sku):
            continue
        level = stock.get(product.sku, data.Stock(0, 0))
        position = level.on_hand + level.on_order
        daily = Fraction(sold[product.sku], WINDOW_DAYS)
        cover = position / daily
        safety = suppliers.get(product.supplier, {}).get('safety_days', DEFAULT_SAFETY_DAYS)
        if cover >= product.lead_time_days + safety:
            continue
        needed = daily * (product.lead_time_days + safety + REVIEW_DAYS) - position
        cases = max(math.ceil(needed / product.case_size), 1)
        found.append(Suggestion(product, level.on_hand, level.on_order, daily, cover, cases))
    return sorted(found, key=lambda s: (s.product.supplier, s.days_of_cover, s.product.sku))


def fixed(value, places):
    """A Fraction rounded half up to `places` decimals, as text."""
    scaled = value * 10 ** places
    rounded = math.floor(scaled + Fraction(1, 2))
    return f'{rounded / 10 ** places:.{places}f}'


def row(suggestion):
    return [suggestion.product.sku, suggestion.product.name, suggestion.on_hand, suggestion.on_order,
            fixed(suggestion.daily_sales, 2), fixed(suggestion.days_of_cover, 1), suggestion.cases, suggestion.units]
