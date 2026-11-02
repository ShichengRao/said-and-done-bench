"""Prices for holds, from the pricing service.

Quotes come from a local cache of the price list. A cached price expires
after a few minutes and is then refetched from the pricing service, which
takes about 20 ms. There's no pricing service outside production, so the
stand-in below sleeps instead, about as often as production misses its cache
during a sale (one quote in 1,200).
"""

from __future__ import annotations

import random
import time

LIST_PRICES = {"lantern": 2_500, "stove": 8_999, "tarp": 1_200, "canteen": 1_450, "compass": 1_999}
REFETCH_CHANCE = 1 / 1200
REFETCH_SECONDS = 0.02


class PriceBook:
    def __init__(self, prices: dict[str, int] | None = None, refetch_chance: float = REFETCH_CHANCE,
                 refetch_seconds: float = REFETCH_SECONDS):
        self._prices = dict(prices or LIST_PRICES)
        self.refetch_chance = refetch_chance
        self.refetch_seconds = refetch_seconds

    def quote(self, sku: str, units: int) -> int:
        """The price in cents of `units` of `sku`."""
        if sku not in self._prices:
            raise ValueError(f"no price for {sku!r}")
        if random.random() < self.refetch_chance:
            time.sleep(self.refetch_seconds)  # the cached price expired: refetch it
        return self._prices[sku] * units
