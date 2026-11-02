"""The three tables a Shop keeps its state in.

In production these are tables in the warehouse database (the platform repo's
warehouse/tables.py). Each method below runs as one SQL statement, and the
tables do no locking of their own. Shop code only calls these methods:

    StockTable      get(sku) -> units on hand; put(sku, units)
    HoldTable       place(order_id, sku, units, price_cents); release(order_id);
                    units_held(sku) -> int; holds() -> list[Hold]
    BackorderQueue  push(order); waiting(sku) -> list[Order], oldest first;
                    remove(order_id)

The Memory* classes are the in-process stand-ins used in development and
tests. Their locks only keep each dict consistent, the way each statement is
atomic in the database.
"""

from __future__ import annotations

import threading

from holdfast.models import Hold, Order


class MemoryStockTable:
    def __init__(self, units: dict[str, int] | None = None):
        self._units = dict(units or {})
        self._lock = threading.Lock()

    def get(self, sku: str) -> int:
        with self._lock:
            return self._units.get(sku, 0)

    def put(self, sku: str, units: int) -> None:
        with self._lock:
            self._units[sku] = units


class MemoryHoldTable:
    def __init__(self):
        self._holds: dict[str, Hold] = {}
        self._lock = threading.Lock()

    def place(self, order_id: str, sku: str, units: int, price_cents: int) -> None:
        with self._lock:
            if order_id in self._holds:
                raise ValueError(f"order {order_id} already has a hold")
            self._holds[order_id] = Hold(order_id, sku, units, price_cents)

    def release(self, order_id: str) -> None:
        with self._lock:
            self._holds.pop(order_id, None)

    def units_held(self, sku: str) -> int:
        with self._lock:
            return sum(hold.units for hold in self._holds.values() if hold.sku == sku)

    def holds(self) -> list[Hold]:
        with self._lock:
            return list(self._holds.values())


class MemoryBackorderQueue:
    def __init__(self):
        self._orders: list[Order] = []
        self._lock = threading.Lock()

    def push(self, order: Order) -> None:
        with self._lock:
            self._orders.append(order)

    def waiting(self, sku: str) -> list[Order]:
        with self._lock:
            return [order for order in self._orders if order.sku == sku]

    def remove(self, order_id: str) -> None:
        with self._lock:
            self._orders = [order for order in self._orders if order.id != order_id]
