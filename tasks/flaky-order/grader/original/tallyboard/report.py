"""Plain-text reports: totals by region or by product, with sales tax."""

from __future__ import annotations

from collections import defaultdict

from tallyboard.money import format_cents
from tallyboard.tax import tax_total


def render(sales, title: str = "Sales summary") -> str:
    """Units and revenue per region, highest revenue first, then totals and tax."""
    return _table(title, "Region", sales, key=lambda sale: sale.region.name)


def render_products(sales, title: str = "Sales by product") -> str:
    """Units and revenue per product, highest revenue first, then totals and tax."""
    return _table(title, "Product", sales, key=lambda sale: sale.product)


def _table(title, label, sales, key) -> str:
    units, revenue = defaultdict(int), defaultdict(int)
    for sale in sales:
        units[key(sale)] += sale.quantity
        revenue[key(sale)] += sale.amount_cents
    lines = [title, "=" * len(title)]
    if not revenue:
        lines.append("No sales.")
    else:
        lines.append(f"{label:<12}{'Units':>8}{'Revenue':>14}")
        for name in sorted(revenue, key=lambda name: (-revenue[name], name)):
            lines.append(f"{name:<12}{units[name]:>8}{format_cents(revenue[name]):>14}")
        lines.append(f"{'Total':<12}{sum(units.values()):>8}{format_cents(sum(revenue.values())):>14}")
        lines.append(f"{'Sales tax':<20}{format_cents(tax_total(sales)):>14}")
    return "\n".join(lines) + "\n"
