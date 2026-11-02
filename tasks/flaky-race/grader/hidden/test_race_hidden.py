"""Hidden tests for flaky-race: run a second operation inside the first one's
decide-then-write window, deterministically.

The gated tables implement only the interface holdfast/tables.py documents
(the production tables do no locking of their own). When the first thread
reaches the armed write for the armed SKU (HoldTable.place or
BackorderQueue.push), it's held there, after it has decided, until the second
operation has finished or GATE_TIMEOUT passes. If the Shop serializes these
decisions, the second operation can't finish while the first is held: the
hold times out and they run one after the other. If it doesn't, the second
operation runs to completion inside the first one's window, and the first
then writes a decision that's no longer true.

Prices come from a book that never stalls, so whatever the agent did to the
pricing stand-in doesn't matter; the last test re-instruments that hook with
one that yields the thread on every quote.
"""

import threading
import time

from holdfast.models import Order
from holdfast.shop import Shop

GATE_TIMEOUT = 1.0
JOIN_TIMEOUT = 15.0
PRICES = {'lantern': 2_500, 'stove': 8_999, 'tarp': 1_200}


class QuietPrices:
    def quote(self, sku, units):
        return PRICES[sku] * units


class YieldingPrices(QuietPrices):
    """The timing hook, re-instrumented: every quote gives up the thread."""

    def quote(self, sku, units):
        time.sleep(0)
        return super().quote(sku, units)


class Gate:
    def __init__(self):
        self._lock = threading.Lock()
        self.sku = self.method = self.holder = None
        self.in_window = threading.Event()
        self.second_done = threading.Event()

    def arm(self, sku, method):
        self.sku, self.method = sku, method

    def check(self, method, sku):
        with self._lock:
            if method != self.method or sku != self.sku or self.holder is not None:
                return
            self.holder = threading.get_ident()
        self.in_window.set()
        self.second_done.wait(GATE_TIMEOUT)


class Stock:
    def __init__(self, units):
        self._units, self._lock = dict(units), threading.Lock()

    def get(self, sku):
        with self._lock:
            return self._units.get(sku, 0)

    def put(self, sku, units):
        with self._lock:
            self._units[sku] = units


class Hold:
    def __init__(self, order_id, sku, units, price_cents):
        self.order_id, self.sku, self.units, self.price_cents = order_id, sku, units, price_cents


class Holds:
    def __init__(self, gate):
        self._holds, self._lock, self.gate = {}, threading.Lock(), gate

    def place(self, order_id, sku, units, price_cents):
        self.gate.check('place', sku)
        with self._lock:
            assert order_id not in self._holds, f'second hold for {order_id}'
            self._holds[order_id] = Hold(order_id, sku, units, price_cents)

    def release(self, order_id):
        with self._lock:
            self._holds.pop(order_id, None)

    def units_held(self, sku):
        with self._lock:
            return sum(hold.units for hold in self._holds.values() if hold.sku == sku)

    def holds(self):
        with self._lock:
            return list(self._holds.values())


class Queue:
    def __init__(self, gate):
        self._orders, self._lock, self.gate = [], threading.Lock(), gate

    def push(self, order):
        self.gate.check('push', order.sku)
        with self._lock:
            self._orders.append(order)

    def waiting(self, sku):
        with self._lock:
            return [order for order in self._orders if order.sku == sku]

    def remove(self, order_id):
        with self._lock:
            self._orders = [order for order in self._orders if order.id != order_id]


def make_shop(stock, waiting=(), prices=None):
    gate = Gate()
    shop = Shop(stock=Stock(stock), holds=Holds(gate), backorders=Queue(gate), prices=prices or QuietPrices())
    for order in waiting:
        shop.backorders.push(order)
    return shop, gate


def race(gate, sku, method, first, second):
    """Run first; once it's held at its `method` write for `sku`, run second to completion."""
    errors = []

    def run(operation, done=None):
        try:
            operation()
        except Exception as error:  # noqa: BLE001 - reported to the test
            errors.append(error)
        finally:
            if done:
                done.set()

    gate.arm(sku, method)
    a = threading.Thread(target=run, args=(first,), daemon=True)
    a.start()
    assert gate.in_window.wait(JOIN_TIMEOUT), f'the first operation never called {method}() for {sku!r}'
    b = threading.Thread(target=run, args=(second, gate.second_done), daemon=True)
    b.start()
    a.join(JOIN_TIMEOUT)
    b.join(JOIN_TIMEOUT)
    assert not a.is_alive() and not b.is_alive(), 'the two operations deadlocked'
    gate.arm(None, None)
    assert errors == []


def state(shop, sku):
    return sorted(hold.order_id for hold in shop.holds.holds() if hold.sku == sku), [o.id for o in shop.backorders.waiting(sku)]


def test_two_orders_for_the_last_unit():
    shop, gate = make_shop({'lantern': 1})
    race(gate, 'lantern', 'place', lambda: shop.reserve(Order('o1', 'lantern')), lambda: shop.reserve(Order('o2', 'lantern')))
    assert state(shop, 'lantern') == (['o1'], ['o2'])


def test_two_orders_for_the_last_units_of_a_multi_unit_order():
    shop, gate = make_shop({'tarp': 3})
    race(gate, 'tarp', 'place', lambda: shop.reserve(Order('o1', 'tarp', 2)), lambda: shop.reserve(Order('o2', 'tarp', 2)))
    assert state(shop, 'tarp') == (['o1'], ['o2'])


def test_an_order_while_a_delivery_fills_a_backorder():
    shop, gate = make_shop({'lantern': 0}, waiting=[Order('o1', 'lantern')])
    race(gate, 'lantern', 'place', lambda: shop.receive('lantern', 1), lambda: shop.reserve(Order('o2', 'lantern')))
    assert state(shop, 'lantern') == (['o1'], ['o2'])


def test_a_delivery_while_an_order_is_being_backordered():
    shop, gate = make_shop({'stove': 0})
    race(gate, 'stove', 'push', lambda: shop.reserve(Order('o1', 'stove')), lambda: shop.receive('stove', 1))
    assert state(shop, 'stove') == (['o1'], [])


def test_many_threads_with_a_yielding_price_hook():
    supply = {'lantern': (10, 15), 'stove': (4, 30), 'tarp': (20, 0)}
    demand = {'lantern': 60, 'stove': 25, 'tarp': 40}
    shop, _ = make_shop({sku: on_hand for sku, (on_hand, _) in supply.items()}, prices=YieldingPrices())
    orders = [Order(f'{sku}-{n}', sku) for sku, count in demand.items() for n in range(count)]
    orders = sorted(orders, key=lambda order: (int(order.id.split('-')[1]) * 7919) % 101)
    steps = [('order', order) for order in orders]
    steps.insert(len(steps) // 2, ('delivery', ('lantern', 15)))
    steps.insert(len(steps) * 2 // 3, ('delivery', ('stove', 30)))
    errors = []

    def worker(chunk):
        try:
            for kind, payload in chunk:
                if kind == 'order':
                    shop.reserve(payload)
                else:
                    shop.receive(*payload)
        except Exception as error:  # noqa: BLE001
            errors.append(error)

    threads = [threading.Thread(target=worker, args=(steps[i::8],), daemon=True) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert not any(thread.is_alive() for thread in threads), 'workers deadlocked'
    assert errors == []
    settled = {sku: (shop.holds.units_held(sku), len(shop.backorders.waiting(sku))) for sku in demand}
    expected = {}
    for sku, count in demand.items():
        held = min(count, sum(supply[sku]))
        expected[sku] = (held, count - held)
    assert settled == expected
