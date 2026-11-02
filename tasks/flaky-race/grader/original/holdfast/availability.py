"""How many units of a SKU can still be held."""

from __future__ import annotations


def available(stock, holds, sku: str) -> int:
    return stock.get(sku) - holds.units_held(sku)
