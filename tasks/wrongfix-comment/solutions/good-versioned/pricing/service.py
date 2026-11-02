"""Quotes: a customer's contract price for a SKU, read through the quote cache.

No lock is held while the backend is asked for a price: each pair has a
version that update_price bumps, and a miss only caches what it read if the
version didn't change while it was reading.
"""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from itertools import count

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
        self._ticket = count(1)
        self._versions = defaultdict(int)

    def get_quote(self, customer_id: str, sku: str) -> Quote:
        check_customer_id(customer_id)
        check_sku(sku)
        key = quote_key(customer_id, sku)
        price = self.cache.get(key)
        if price is not None:
            return Quote(customer_id, sku, price, cached=True)
        version = self._versions[key]
        price = self.backend.get_price(customer_id, sku)
        if self._versions[key] == version:
            self.cache.set(key, price)
            if self._versions[key] != version:  # An update landed meanwhile.
                self.cache.delete(key)
        return Quote(customer_id, sku, price, cached=False)

    def update_price(self, customer_id: str, sku: str, price: Decimal) -> None:
        """Called by the ERP sync whenever a contract price is written."""
        check_customer_id(customer_id)
        check_sku(sku)
        key = quote_key(customer_id, sku)
        self._versions[key] = next(self._ticket)
        self.backend.set_price(customer_id, sku, Decimal(price))
        self.cache.delete(key)
