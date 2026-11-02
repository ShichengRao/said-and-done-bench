"""Quotes: a customer's contract price for a SKU, read through the quote cache."""

import threading
from dataclasses import dataclass
from decimal import Decimal

from pricing.backend import PricingBackend
from pricing.cache import TTLCache
from pricing.ids import check_customer_id, check_sku
from pricing.keys import quote_key


@dataclass(frozen=True)
class Quote:
    customer_id: str
    sku: str
    price: Decimal
    cached: bool  # Served from the cache rather than the backend.


class QuoteService:
    def __init__(self, backend: PricingBackend, cache: TTLCache | None = None):
        self.backend = backend
        self.cache = cache if cache is not None else TTLCache()
        # A miss and an update of the same price mustn't interleave, or the
        # miss can write back the price the update replaced.
        self._lock = threading.Lock()

    def get_quote(self, customer_id: str, sku: str) -> Quote:
        check_customer_id(customer_id)
        check_sku(sku)
        key = quote_key(customer_id, sku)
        price = self.cache.get(key)
        if price is not None:
            return Quote(customer_id, sku, price, cached=True)
        with self._lock:
            price = self.cache.get(key)
            if price is not None:
                return Quote(customer_id, sku, price, cached=True)
            price = self.backend.get_price(customer_id, sku)
            self.cache.set(key, price)
            return Quote(customer_id, sku, price, cached=False)

    def update_price(self, customer_id: str, sku: str, price: Decimal) -> None:
        """Called by the ERP sync whenever a contract price is written."""
        check_customer_id(customer_id)
        check_sku(sku)
        with self._lock:
            self.backend.set_price(customer_id, sku, Decimal(price))
            self.cache.delete(quote_key(customer_id, sku))
