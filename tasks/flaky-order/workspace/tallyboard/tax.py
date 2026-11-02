"""Sales tax, at each sale's regional rate, rounded half up to the cent."""

from __future__ import annotations


def tax_cents(sale) -> int:
    """Tax on one sale; a return (negative quantity) gets negative tax."""
    amount = sale.amount_cents
    sign = -1 if amount < 0 else 1
    return sign * ((abs(amount) * sale.region.tax_rate_bp + 5_000) // 10_000)


def tax_total(sales) -> int:
    return sum(tax_cents(sale) for sale in sales)
