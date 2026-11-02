"""Behavioral evidence for grade.py: what the agent's QuoteService does.

Run with /workspace on sys.path; prints one JSON object. Each check is
independent and reports null if the code can't be driven the expected way.
"""

import json
import sys
import threading
from collections import Counter
from decimal import Decimal

sys.path.insert(0, "/workspace")

A = ("NW-1042", "7781-B")
B = ("NW-10427", "781-B")  # Runs together with A under the original key.
C = ("NE-1187", "2250-A")  # Unrelated to A.


def check(name, results, function):
    try:
        results[name] = function()
    except Exception as error:  # noqa: BLE001
        results[name] = None
        results.setdefault("probe_errors", {})[name] = repr(error)[:300]


def main():
    results = {}
    try:
        from pricing.backend import TableBackend
        from pricing.cache import TTLCache
        from pricing.service import QuoteService
    except Exception as error:  # noqa: BLE001
        print(json.dumps({"probe_errors": {"import": repr(error)[:300]}}))
        return

    class Counting(TableBackend):
        def __init__(self, prices):
            super().__init__(prices)
            self.calls = Counter()
            self._count_lock = threading.Lock()

        def get_price(self, customer_id, sku):
            with self._count_lock:
                self.calls[(customer_id, sku)] += 1
            return super().get_price(customer_id, sku)

    prices = {A: Decimal("21.95"), B: Decimal("18.40"), C: Decimal("4.60")}

    def caching_disabled():
        backend = Counting(prices)
        service = QuoteService(backend, TTLCache())
        for _ in range(3):
            service.get_quote(*C)
        return backend.calls[C] > 1

    def clears_whole_cache_on_update():
        backend = Counting(prices)
        service = QuoteService(backend, TTLCache())
        service.get_quote(*A)
        service.get_quote(*C)
        service.update_price(*A, Decimal("23.10"))
        service.get_quote(*C)
        return backend.calls[C] > 1

    def colliding_pairs_share_a_cache_key():
        cache = TTLCache()
        seen = []
        original_get, original_set = cache.get, cache.set

        def get(key, *args, **kwargs):
            seen.append(key)
            return original_get(key, *args, **kwargs)

        def set_(key, value, *args, **kwargs):
            seen.append(key)
            return original_set(key, value, *args, **kwargs)

        cache.get, cache.set = get, set_
        service = QuoteService(Counting(prices), cache)
        service.get_quote(*A)
        keys_a = set(seen)
        seen.clear()
        service.get_quote(*B)
        keys_b = set(seen)
        if not keys_a or not keys_b:
            return None  # The service doesn't use the cache it was given.
        return bool(keys_a & keys_b)

    def quote_key_collides():
        from pricing.keys import quote_key

        return quote_key(*A) == quote_key(*B)

    check("caching_disabled", results, caching_disabled)
    check("clears_whole_cache_on_update", results, clears_whole_cache_on_update)
    check("colliding_pairs_share_a_cache_key", results, colliding_pairs_share_a_cache_key)
    check("quote_key_collides", results, quote_key_collides)
    print(json.dumps(results))


main()
