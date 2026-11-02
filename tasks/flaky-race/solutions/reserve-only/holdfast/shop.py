"""A Shop: the tables, the price book, and the services that act on them.

One Shop is shared by the storefront's request threads, the warehouse
integration that reports deliveries, and flash-sale batches (sale.py).
"""

from __future__ import annotations

import threading

from holdfast import checkout, receiving
from holdfast.availability import available
from holdfast.backorders import BackorderDesk
from holdfast.events import EventBus
from holdfast.models import Order, Reservation
from holdfast.pricing import PriceBook
from holdfast.tables import MemoryBackorderQueue, MemoryHoldTable, MemoryStockTable


class Shop:
    def __init__(self, stock=None, holds=None, backorders=None, prices=None):
        self.stock = stock if stock is not None else MemoryStockTable()
        self.holds = holds if holds is not None else MemoryHoldTable()
        self.backorders = backorders if backorders is not None else MemoryBackorderQueue()
        self.prices = prices if prices is not None else PriceBook()
        # Deciding to hold or backorder reads two tables and then writes one,
        # and the tables don't lock, so every such decision runs under this
        # lock: checkout, filling backorders, and receiving (which fills them).
        self.lock = threading.RLock()
        self.events = EventBus()
        self.backorder_desk = BackorderDesk(self)
        self.events.subscribe("stock.received", self.backorder_desk.on_stock_received)

    def reserve(self, order: Order) -> Reservation:
        return checkout.reserve(self, order)

    def receive(self, sku: str, units: int) -> int:
        return receiving.receive(self, sku, units)

    def available(self, sku: str) -> int:
        return available(self.stock, self.holds, sku)
