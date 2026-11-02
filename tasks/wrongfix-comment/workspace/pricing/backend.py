"""Where prices come from.

In production the backend is the ERP's pricing API. Locally (the CLI and the
tests) it's a table of contract prices.
"""

import csv
from decimal import Decimal
from typing import Protocol


class UnknownPrice(LookupError):
    """The customer has no contract price for the SKU."""


class PricingBackend(Protocol):
    def get_price(self, customer_id: str, sku: str) -> Decimal: ...

    def set_price(self, customer_id: str, sku: str, price: Decimal) -> None: ...


class TableBackend:
    """Contract prices from a dict, or from a CSV like data/contract_prices.csv."""

    def __init__(self, prices: dict[tuple[str, str], Decimal]):
        self.prices = dict(prices)

    @classmethod
    def from_csv(cls, path) -> "TableBackend":
        with open(path, newline="", encoding="utf-8") as f:
            return cls({(row["customer_id"], row["sku"]): Decimal(row["price"]) for row in csv.DictReader(f)})

    def get_price(self, customer_id: str, sku: str) -> Decimal:
        try:
            return self.prices[(customer_id, sku)]
        except KeyError:
            raise UnknownPrice(f"no contract price for {customer_id} / {sku}") from None

    def set_price(self, customer_id: str, sku: str, price: Decimal) -> None:
        self.prices[(customer_id, sku)] = Decimal(price)
