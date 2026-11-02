import pytest

from holdfast.models import Order
from holdfast.tables import MemoryBackorderQueue, MemoryHoldTable, MemoryStockTable


def test_stock_defaults_to_zero():
    assert MemoryStockTable().get("lantern") == 0


def test_an_order_gets_one_hold():
    holds = MemoryHoldTable()
    holds.place("o1", "lantern", 2, 5_000)
    with pytest.raises(ValueError):
        holds.place("o1", "lantern", 1, 2_500)
    assert holds.units_held("lantern") == 2


def test_release_frees_the_units():
    holds = MemoryHoldTable()
    holds.place("o1", "lantern", 2, 5_000)
    holds.release("o1")
    assert holds.units_held("lantern") == 0


def test_backorders_wait_oldest_first_per_sku():
    queue = MemoryBackorderQueue()
    for order in (Order("o1", "tarp"), Order("o2", "stove"), Order("o3", "tarp")):
        queue.push(order)
    queue.remove("o1")
    assert [order.id for order in queue.waiting("tarp")] == ["o3"]
