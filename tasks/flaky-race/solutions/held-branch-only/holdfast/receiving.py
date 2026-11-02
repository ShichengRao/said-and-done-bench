"""Receiving: deliveries add to stock on hand."""

from __future__ import annotations


def receive(shop, sku: str, units: int) -> int:
    """Add a delivery to stock and announce it; returns the new units on hand."""
    if units <= 0:
        raise ValueError("a delivery needs at least one unit")
    with shop.lock:
        on_hand = shop.stock.get(sku) + units
        shop.stock.put(sku, on_hand)
        shop.events.publish("stock.received", sku=sku)
        return on_hand
