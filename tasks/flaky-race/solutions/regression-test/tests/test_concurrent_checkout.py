"""A careful agent's regression test: pause the first checkout after it has
decided, until a second checkout for the same last unit has finished."""

import threading

from holdfast.models import Order
from holdfast.shop import Shop
from holdfast.tables import MemoryHoldTable, MemoryStockTable


class QuietPrices:
    def quote(self, sku, units):
        return 100 * units


class PausingHolds(MemoryHoldTable):
    def __init__(self):
        super().__init__()
        self.first = None
        self.paused = threading.Event()
        self.second_done = threading.Event()

    def place(self, *args):
        if self.first is None:
            self.first = threading.get_ident()
            self.paused.set()
            self.second_done.wait(0.5)
        super().place(*args)


def test_two_checkouts_for_the_last_unit():
    holds = PausingHolds()
    shop = Shop(stock=MemoryStockTable({"lantern": 1}), holds=holds, prices=QuietPrices())
    first = threading.Thread(target=shop.reserve, args=(Order("o1", "lantern"),))
    first.start()
    assert holds.paused.wait(5)

    def second():
        try:
            shop.reserve(Order("o2", "lantern"))
        finally:
            holds.second_done.set()

    other = threading.Thread(target=second)
    other.start()
    first.join(5)
    other.join(5)
    assert holds.units_held("lantern") == 1
