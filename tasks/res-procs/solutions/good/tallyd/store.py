"""In-memory counters."""

import threading

MAX_NAME = 200


class InvalidName(ValueError):
    pass


def check_name(name):
    if not isinstance(name, str) or not name or len(name) > MAX_NAME:
        raise InvalidName(f'counter names are 1-{MAX_NAME} characters')
    if not name.isprintable():
        raise InvalidName('counter names must be printable')
    return name


class Store:
    def __init__(self):
        self._counts = {}
        self._deltas = {}  # Increments not yet sent to the ledger.
        self._lock = threading.Lock()

    def incr(self, name, by=1):
        check_name(name)
        if not isinstance(by, int) or isinstance(by, bool):
            raise ValueError('"by" must be an integer')
        with self._lock:
            value = self._counts.get(name, 0) + by
            self._counts[name] = value
            self._deltas[name] = self._deltas.get(name, 0) + by
            return value

    def get(self, name):
        with self._lock:
            return self._counts.get(name)

    def take_deltas(self):
        """The increments since the last call, {name: increment}; they're cleared."""
        with self._lock:
            deltas, self._deltas = self._deltas, {}
            return deltas

    def give_back(self, deltas):
        """Return increments that couldn't be sent, so the next take_deltas() includes them."""
        with self._lock:
            for name, increment in deltas.items():
                self._deltas[name] = self._deltas.get(name, 0) + increment

    def top(self, n):
        with self._lock:
            ranked = sorted(self._counts.items(), key=lambda item: (-item[1], item[0]))
        return ranked[:n]
