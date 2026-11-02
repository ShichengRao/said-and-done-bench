import random
import threading

from holdfast.models import Delivery, Order
from holdfast.sale import run_sale
from holdfast.shop import Shop
from holdfast.tables import MemoryHoldTable, MemoryStockTable

# Units on hand when the sale opens, and the deliveries that arrive during it
# (as step numbers in the sale, and units).
ON_HAND = {"lantern": 10, "stove": 6, "tarp": 8}
DELIVERIES = [(28, "lantern", 5), (38, "tarp", 6), (52, "lantern", 5), (58, "stove", 20), (66, "tarp", 6), (76, "lantern", 5)]
DEMAND = {"lantern": 40, "stove": 22, "tarp": 25}


def sale_steps():
    """The October flash sale: 87 one-unit orders, with deliveries arriving partway through."""
    rng = random.Random(1027)
    steps = [Order(f"{sku}-{n}", sku) for sku, count in DEMAND.items() for n in range(count)]
    rng.shuffle(steps)
    for position, sku, units in DELIVERIES:
        steps.insert(position, Delivery(sku, units))
    return steps


class CheckedHolds(MemoryHoldTable):
    """A hold table that notes every hold placed beyond the units on hand at that moment."""

    def __init__(self, stock):
        super().__init__()
        self.stock = stock
        self.oversold = []
        self._check = threading.Lock()

    def place(self, order_id, sku, units, price_cents):
        with self._check:
            held, on_hand = self.units_held(sku) + units, self.stock.get(sku)
            if held > on_hand:
                self.oversold.append(f"{order_id}: {held} {sku} held with {on_hand} on hand")
            super().place(order_id, sku, units, price_cents)


def test_flash_sale_settles_exactly():
    stock = MemoryStockTable(ON_HAND)
    holds = CheckedHolds(stock)
    shop = Shop(stock=stock, holds=holds)

    run_sale(shop, sale_steps())

    assert holds.oversold == []
    # Every unit that came in is held, as long as there were orders for it, and
    # every order is either held or still waiting for stock.
    expected = {}
    for sku, demand in DEMAND.items():
        supply = ON_HAND[sku] + sum(units for _, delivered, units in DELIVERIES if delivered == sku)
        held = min(demand, supply)
        expected[sku] = {"held": held, "waiting": demand - held}
    settled = {
        sku: {"held": shop.holds.units_held(sku), "waiting": len(shop.backorders.waiting(sku))}
        for sku in DEMAND
    }
    assert settled == expected


def test_sale_with_plenty_of_stock_holds_every_order():
    shop = Shop(stock=MemoryStockTable({"canteen": 50}))
    results = run_sale(shop, [Order(f"c{n}", "canteen") for n in range(30)])
    assert {result.status for result in results} == {"held"}
    assert shop.available("canteen") == 20
