"""The quote cache.

In production, quotes go through the shared cache behind the cache proxy.
TTLCache is an in-process stand-in with the same interface that enforces the
proxy's key rules, so code that works against it works against the shared
cache:

- a key is "<namespace>:<body>", and the body can't contain another ':'
  (the proxy routes on the namespace);
- no whitespace or control characters;
- at most 64 bytes.
"""

import threading
import time

MAX_KEY_BYTES = 64


class InvalidKey(ValueError):
    pass


def check_key(key: str) -> None:
    if not isinstance(key, str):
        raise InvalidKey(f"cache keys are strings, not {type(key).__name__}")
    namespace, sep, body = key.partition(":")
    if not sep or not namespace or not body:
        raise InvalidKey(f"{key!r} isn't <namespace>:<body>")
    if ":" in body:
        raise InvalidKey(f"{key!r} has more than one ':'")
    if any(ch.isspace() or not ch.isprintable() for ch in key):
        raise InvalidKey(f"{key!r} has whitespace or control characters")
    if len(key.encode("utf-8")) > MAX_KEY_BYTES:
        raise InvalidKey(f"{key!r} is longer than {MAX_KEY_BYTES} bytes")


class TTLCache:
    """Entries expire ttl_seconds after they're set. Each call is atomic, as on the shared cache."""

    def __init__(self, ttl_seconds: float = 300.0, clock=time.monotonic):
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries = {}
        self._mutex = threading.Lock()

    def get(self, key):
        check_key(key)
        with self._mutex:
            entry = self._entries.get(key)
            if entry is None:
                return None
            value, expires = entry
            if self._clock() >= expires:
                del self._entries[key]
                return None
            return value

    def set(self, key, value) -> None:
        check_key(key)
        with self._mutex:
            self._entries[key] = (value, self._clock() + self.ttl_seconds)

    def delete(self, key) -> None:
        check_key(key)
        with self._mutex:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._mutex:
            self._entries.clear()

    def __len__(self) -> int:
        with self._mutex:
            return len(self._entries)
