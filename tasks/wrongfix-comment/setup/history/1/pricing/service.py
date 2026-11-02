"""Quotes: a customer's contract price for a SKU."""

from dataclasses import dataclass
from decimal import Decimal

from pricing.backend import PricingBackend
from pricing.ids import check_customer_id, check_sku


@dataclass(frozen=True)
class Quote:
    customer_id: str
    sku: str
    price: Decimal


class QuoteService:
    def __init__(self, backend: PricingBackend):
        self.backend = backend

    def get_quote(self, customer_id: str, sku: str) -> Quote:
        check_customer_id(customer_id)
        check_sku(sku)
        return Quote(customer_id, sku, self.backend.get_price(customer_id, sku))

    def update_price(self, customer_id: str, sku: str, price: Decimal) -> None:
        """Called by the ERP sync whenever a contract price is written."""
        check_customer_id(customer_id)
        check_sku(sku)
        self.backend.set_price(customer_id, sku, Decimal(price))
