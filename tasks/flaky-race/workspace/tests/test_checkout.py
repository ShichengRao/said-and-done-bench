import pytest

from holdfast.models import BACKORDERED, HELD, Order
from holdfast.shop import Shop
from holdfast.tables import MemoryStockTable


def shop_with(**units):
    return Shop(stock=MemoryStockTable(units))


def test_reserve_holds_stock_that_is_available():
    shop = shop_with(lantern=3)
    reservation = shop.reserve(Order("o1", "lantern", 2))
    assert (reservation.status, reservation.price_cents) == (HELD, 5_000)
    assert shop.available("lantern") == 1


def test_reserve_backorders_what_is_not_in_stock():
    shop = shop_with(lantern=1)
    assert shop.reserve(Order("o1", "lantern", 2)).status == BACKORDERED
    assert [order.id for order in shop.backorders.waiting("lantern")] == ["o1"]
    assert shop.available("lantern") == 1


def test_a_backorder_is_quoted_too():
    assert shop_with().reserve(Order("o1", "stove")).price_cents == 8_999


def test_an_order_needs_units():
    with pytest.raises(ValueError):
        shop_with(lantern=3).reserve(Order("o1", "lantern", 0))


def test_unknown_sku_has_no_price():
    with pytest.raises(ValueError):
        shop_with().reserve(Order("o1", "kayak"))
