"""Checkout: hold stock for an order, or put it on backorder."""

from __future__ import annotations

from holdfast.availability import available
from holdfast.models import BACKORDERED, HELD, Order, Reservation


def reserve(shop, order: Order) -> Reservation:
    """Hold the order's units if they're in stock; otherwise backorder it.

    Either way the customer is quoted the current price, and a backorder keeps
    that price when it's filled later.
    """
    if order.units <= 0:
        raise ValueError("an order needs at least one unit")
    with shop.lock:
        in_stock = available(shop.stock, shop.holds, order.sku)
        price = shop.prices.quote(order.sku, order.units)
        if in_stock >= order.units:
            shop.holds.place(order.id, order.sku, order.units, price)
            return Reservation(order.id, HELD, price)
        shop.backorders.push(order)
        return Reservation(order.id, BACKORDERED, price)
