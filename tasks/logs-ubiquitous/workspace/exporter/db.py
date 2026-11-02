"""Connections to the ledger replica, from a fixed-size pool.

In production the export runs inside the exp-worker job runner, which shares
one 'ledger-replica' pool between all the nightly jobs, so at 02:00 a
connection isn't always free right away. acquire() waits up to
acquire_timeout seconds for one, logs the timeout, backs off, and tries
again, up to `attempts` tries in all.
"""

import contextlib
import logging
import queue
import time

log = logging.getLogger(__name__)


class PoolTimeout(Exception):
    """No connection came free in time."""


class ConnectionPool:
    def __init__(self, connect, *, name="ledger-replica", size=4, acquire_timeout=2.0, attempts=5, backoff=0.5):
        self.name = name
        self.size = size
        self.acquire_timeout = acquire_timeout
        self.attempts = attempts
        self.backoff = backoff
        self._connect = connect
        self._idle = queue.LifoQueue()
        for _ in range(size):
            self._idle.put(None)  # A free slot, connected on first use.

    @property
    def in_use(self) -> int:
        return self.size - self._idle.qsize()

    def _acquire_once(self):
        try:
            conn = self._idle.get(timeout=self.acquire_timeout)
        except queue.Empty as error:
            raise PoolTimeout(f"no connection free in pool {self.name!r} after {self.acquire_timeout}s") from error
        return conn if conn is not None else self._connect()

    def acquire(self):
        started = time.monotonic()
        for attempt in range(1, self.attempts + 1):
            try:
                conn = self._acquire_once()
            except PoolTimeout:
                log.exception(
                    "failed to acquire a connection from pool %r within %.1fs (%d of %d in use)",
                    self.name, self.acquire_timeout, self.in_use, self.size,
                )
                if attempt == self.attempts:
                    raise
                delay = self.backoff * attempt
                log.warning("retrying in %.1fs (attempt %d of %d)", delay, attempt + 1, self.attempts)
                time.sleep(delay)
                continue
            if attempt > 1:
                log.info("acquired a connection on attempt %d (waited %.2fs)", attempt, time.monotonic() - started)
            return conn
        raise AssertionError("unreachable")

    def release(self, conn) -> None:
        self._idle.put(conn)

    @contextlib.contextmanager
    def connection(self):
        conn = self.acquire()
        try:
            yield conn
        finally:
            self.release(conn)
