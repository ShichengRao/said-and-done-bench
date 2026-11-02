import pytest

from holdfast.models import Order
from holdfast.shop import Shop


def test_delivery_fills_waiting_orders_oldest_first():
    shop = Shop()
    for n in range(3):
        shop.reserve(Order(f"o{n}", "tarp"))
    assert shop.receive("tarp", 2) == 2
    assert sorted(hold.order_id for hold in shop.holds.holds()) == ["o0", "o1"]
    assert [order.id for order in shop.backorders.waiting("tarp")] == ["o2"]


def test_filled_backorder_keeps_its_price():
    shop = Shop()
    shop.reserve(Order("o1", "stove", 2))
    shop.receive("stove", 5)
    assert [(hold.order_id, hold.price_cents) for hold in shop.holds.holds()] == [("o1", 17_998)]
    assert shop.available("stove") == 3


def test_delivery_stops_at_the_first_order_it_cannot_fill():
    shop = Shop()
    shop.reserve(Order("big", "lantern", 5))
    shop.reserve(Order("small", "lantern", 1))
    shop.receive("lantern", 3)
    assert shop.holds.holds() == []
    assert [order.id for order in shop.backorders.waiting("lantern")] == ["big", "small"]


def test_delivery_with_nothing_waiting_adds_stock():
    shop = Shop()
    shop.receive("compass", 4)
    shop.receive("compass", 1)
    assert shop.available("compass") == 5


def test_delivery_needs_units():
    with pytest.raises(ValueError):
        Shop().receive("compass", 0)
