"""The records a Shop deals in."""

from __future__ import annotations

import dataclasses

HELD = "held"
BACKORDERED = "backordered"


@dataclasses.dataclass(frozen=True)
class Order:
    id: str
    sku: str
    units: int = 1


@dataclasses.dataclass(frozen=True)
class Hold:
    order_id: str
    sku: str
    units: int
    price_cents: int


@dataclasses.dataclass(frozen=True)
class Delivery:
    """A shipment arriving at the warehouse."""

    sku: str
    units: int


@dataclasses.dataclass(frozen=True)
class Reservation:
    order_id: str
    status: str  # HELD or BACKORDERED
    price_cents: int
