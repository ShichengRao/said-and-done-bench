"""Filling backorders when stock comes in."""

from __future__ import annotations

from holdfast.availability import available


class BackorderDesk:
    """Fills waiting orders, oldest first, whenever a SKU is restocked."""

    def __init__(self, shop):
        self.shop = shop

    def on_stock_received(self, sku: str) -> None:
        shop = self.shop
        with shop.lock:
            for order in shop.backorders.waiting(sku):
                if available(shop.stock, shop.holds, sku) < order.units:
                    break
                price = shop.prices.quote(order.sku, order.units)
                shop.holds.place(order.id, order.sku, order.units, price)
                shop.backorders.remove(order.id)
