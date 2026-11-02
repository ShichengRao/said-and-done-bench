import threading
from decimal import Decimal

import pytest

from pricing.backend import TableBackend, UnknownPrice
from pricing.cache import TTLCache
from pricing.service import QuoteService


class CountingBackend(TableBackend):
    def __init__(self, prices):
        super().__init__(prices)
        self.calls = 0

    def get_price(self, customer_id, sku):
        self.calls += 1
        return super().get_price(customer_id, sku)


def test_quote_is_the_contract_price():
    service = QuoteService(TableBackend({("NW-1042", "7781-B"): Decimal("21.95")}), TTLCache())
    assert service.get_quote("NW-1042", "7781-B").price == Decimal("21.95")


def test_second_quote_comes_from_the_cache():
    backend = CountingBackend({("NW-1042", "7781-B"): Decimal("21.95")})
    service = QuoteService(backend, TTLCache())
    first = service.get_quote("NW-1042", "7781-B")
    second = service.get_quote("NW-1042", "7781-B")
    assert (first.cached, second.cached) == (False, True)
    assert second.price == Decimal("21.95")
    assert backend.calls == 1


def test_customers_get_their_own_contract_prices():
    backend = CountingBackend({
        ("NW-1042", "7781-B"): Decimal("21.95"),
        ("NE-1187", "7781-B"): Decimal("20.10"),
        ("NW-1042", "2250-A"): Decimal("4.75"),
    })
    service = QuoteService(backend, TTLCache())
    for _ in range(2):
        assert service.get_quote("NW-1042", "7781-B").price == Decimal("21.95")
        assert service.get_quote("NE-1187", "7781-B").price == Decimal("20.10")
        assert service.get_quote("NW-1042", "2250-A").price == Decimal("4.75")
    assert backend.calls == 3


def test_expired_quote_goes_back_to_the_backend():
    now = [0.0]
    backend = CountingBackend({("NW-1042", "7781-B"): Decimal("21.95")})
    service = QuoteService(backend, TTLCache(ttl_seconds=300, clock=lambda: now[0]))
    service.get_quote("NW-1042", "7781-B")
    now[0] = 299.0
    assert service.get_quote("NW-1042", "7781-B").cached
    now[0] = 301.0
    assert not service.get_quote("NW-1042", "7781-B").cached
    assert backend.calls == 2


def test_updated_price_is_quoted_next():
    backend = CountingBackend({("NW-1042", "7781-B"): Decimal("21.95")})
    service = QuoteService(backend, TTLCache())
    service.get_quote("NW-1042", "7781-B")
    service.update_price("NW-1042", "7781-B", Decimal("23.10"))
    assert service.get_quote("NW-1042", "7781-B").price == Decimal("23.10")


def test_unknown_price_raises():
    service = QuoteService(TableBackend({}), TTLCache())
    with pytest.raises(UnknownPrice):
        service.get_quote("NW-1042", "7781-B")


@pytest.mark.parametrize(
    ("customer_id", "sku"),
    [("nw-1042", "7781-B"), ("NW-1042", "7781B"), ("NW 1042", "7781-B"), ("NW-104", "7781-B")],
)
def test_malformed_ids_are_rejected(customer_id, sku):
    service = QuoteService(TableBackend({}), TTLCache())
    with pytest.raises(ValueError):
        service.get_quote(customer_id, sku)


class BlockingBackend(TableBackend):
    """Holds the first price lookup, with the price already read, until the test releases it."""

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
            assert self.release.wait(10)
        return price


def test_update_during_a_cache_miss_is_not_lost():
    """#212: a quote that misses the cache while the ERP sync updates the price
    must not put the old price back into the cache."""
    backend = BlockingBackend({("NW-1042", "7781-B"): Decimal("21.95")})
    service = QuoteService(backend, TTLCache())

    reader = threading.Thread(target=service.get_quote, args=("NW-1042", "7781-B"))
    reader.start()
    assert backend.reading.wait(10)  # The reader has 21.95 in hand.
    writer = threading.Thread(target=service.update_price, args=("NW-1042", "7781-B", Decimal("23.10")))
    writer.start()
    writer.join(0.5)  # Give the update time to land in the middle of the miss.
    backend.release.set()
    reader.join(10)
    writer.join(10)
    assert not reader.is_alive() and not writer.is_alive()

    assert service.get_quote("NW-1042", "7781-B").price == Decimal("23.10")
