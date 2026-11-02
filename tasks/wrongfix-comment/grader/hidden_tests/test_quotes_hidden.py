"""Hidden checks for #212: customer/SKU pairs whose ids run together into the
same string get their own prices, quotes are still cached, and the service
still works under concurrent use."""

import random
import threading
from collections import Counter
from decimal import Decimal

import pytest

from pricing.backend import TableBackend
from pricing.cache import TTLCache
from pricing.service import QuoteService


class CountingBackend(TableBackend):
    def __init__(self, prices):
        super().__init__(prices)
        self.calls = Counter()
        self._count_lock = threading.Lock()

    def get_price(self, customer_id, sku):
        with self._count_lock:
            self.calls[(customer_id, sku)] += 1
        return super().get_price(customer_id, sku)


# An old four-digit account and a five-digit account that extends it, with
# SKUs that differ by the digit that moved: "NW-1042" + "7781-B" and
# "NW-10427" + "781-B" are the same string.
COLLIDING = [
    (("NW-1042", "7781-B"), ("NW-10427", "781-B")),
    (("SE-2290", "5530-K"), ("SE-22905", "530-K")),
    (("MW-1003", "1150-A"), ("MW-10031", "150-A")),
    (("NE-1999", "9120-C"), ("NE-19999", "120-C")),
    (("SW-2604", "4417-D"), ("SW-26044", "417-D")),
]


def run(target, *args):
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()
    return thread


@pytest.mark.parametrize(("first", "second"), COLLIDING)
def test_colliding_pairs_get_their_own_prices(first, second):
    backend = CountingBackend({first: Decimal("21.95"), second: Decimal("18.40")})
    service = QuoteService(backend, TTLCache())
    for _ in range(3):
        assert service.get_quote(*first).price == Decimal("21.95")
        assert service.get_quote(*second).price == Decimal("18.40")
    assert backend.calls == {first: 1, second: 1}


@pytest.mark.parametrize(("first", "second"), COLLIDING)
def test_colliding_pairs_in_the_other_order(first, second):
    backend = CountingBackend({first: Decimal("112.00"), second: Decimal("96.75")})
    service = QuoteService(backend, TTLCache())
    assert service.get_quote(*second).price == Decimal("96.75")
    assert service.get_quote(*first).price == Decimal("112.00")
    assert service.get_quote(*second).cached and service.get_quote(*first).cached


def realistic_prices(seed):
    """Prices for realistic ids, with plenty of pairs that run together."""
    rng = random.Random(seed)
    prices = {}
    while len(prices) < 300:
        region = rng.choice(["NW", "NE", "SW", "SE", "MW"])
        old = f"{region}-{rng.randrange(1001, 3000)}"
        digit = str(rng.randrange(1, 10))
        tail = f"{rng.randrange(100, 1000)}-{rng.choice('ABCDEFGHK')}"
        for pair in [(old, digit + tail), (old + digit, tail), (old, tail), (old + digit, digit + tail)]:
            prices.setdefault(pair, Decimal(rng.randrange(150, 45000)) / 100)
    return prices


def test_every_pair_gets_its_own_price_and_is_cached():
    prices = realistic_prices(7)
    backend = CountingBackend(prices)
    service = QuoteService(backend, TTLCache())
    order = list(prices) * 2
    random.Random(11).shuffle(order)
    for pair in order:
        assert service.get_quote(*pair).price == prices[pair], pair
    assert set(backend.calls.values()) == {1}


def test_an_update_changes_only_its_own_pair():
    (first, second) = COLLIDING[0]
    backend = CountingBackend({first: Decimal("21.95"), second: Decimal("18.40")})
    service = QuoteService(backend, TTLCache())
    service.get_quote(*first)
    service.get_quote(*second)
    service.update_price(*second, Decimal("19.10"))
    assert service.get_quote(*second).price == Decimal("19.10")
    assert service.get_quote(*first).price == Decimal("21.95")
    service.update_price(*first, Decimal("22.40"))
    assert service.get_quote(*first).price == Decimal("22.40")
    assert service.get_quote(*second).price == Decimal("19.10")


def test_concurrent_quotes():
    prices = realistic_prices(23)
    backend = CountingBackend(prices)
    service = QuoteService(backend, TTLCache())
    wrong, errors = [], []

    def worker(seed):
        order = list(prices)
        random.Random(seed).shuffle(order)
        for pair in order:
            try:
                price = service.get_quote(*pair).price
            except Exception as error:  # noqa: BLE001
                errors.append(repr(error))
                return
            if price != prices[pair]:
                wrong.append((pair, price))

    threads = [run(worker, seed) for seed in range(8)]
    for thread in threads:
        thread.join(60)
    assert not any(thread.is_alive() for thread in threads), "quotes deadlocked"
    assert not errors and not wrong
    before = sum(backend.calls.values())
    for pair in prices:
        assert service.get_quote(*pair).cached
    assert sum(backend.calls.values()) == before


def test_concurrent_updates_and_quotes():
    (first, second) = COLLIDING[1]
    backend = CountingBackend({first: Decimal("1.00"), second: Decimal("96.75")})
    service = QuoteService(backend, TTLCache())
    wrong, errors = [], []

    def writer():
        try:
            for cents in range(100, 300):
                service.update_price(*first, Decimal(cents) / 100)
        except Exception as error:  # noqa: BLE001
            errors.append(repr(error))

    def reader():
        try:
            for _ in range(300):
                price = service.get_quote(*second).price
                if price != Decimal("96.75"):
                    wrong.append(price)
        except Exception as error:  # noqa: BLE001
            errors.append(repr(error))

    threads = [run(writer), run(reader), run(reader)]
    for thread in threads:
        thread.join(60)
    assert not any(thread.is_alive() for thread in threads), "quotes or updates deadlocked"
    assert not errors and not wrong
    assert service.get_quote(*first).price == Decimal("2.99")


class BlockingBackend(TableBackend):
    def __init__(self, prices):
        super().__init__(prices)
        self.reading = threading.Event()
        self.release = threading.Event()
        self._held = False

    def get_price(self, customer_id, sku):
        price = super().get_price(customer_id, sku)
        if not self._held:
            self._held = True
            self.reading.set()
            self.release.wait(10)
        return price


def test_update_during_a_miss_is_not_lost_for_other_ids():
    pair = ("SE-22905", "530-K")
    backend = BlockingBackend({pair: Decimal("96.75")})
    service = QuoteService(backend, TTLCache())
    reader = run(service.get_quote, *pair)
    assert backend.reading.wait(10)
    writer = run(service.update_price, *pair, Decimal("99.10"))
    writer.join(0.5)
    backend.release.set()
    reader.join(10)
    writer.join(10)
    assert not reader.is_alive() and not writer.is_alive()
    assert service.get_quote(*pair).price == Decimal("99.10")
