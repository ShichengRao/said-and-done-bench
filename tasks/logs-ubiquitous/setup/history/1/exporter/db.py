"""Connections to the ledger replica, from a fixed-size pool.

In production the export runs inside the exp-worker job runner, which shares
one 'ledger-replica' pool between all the nightly jobs. acquire() waits up to
acquire_timeout seconds for a free connection.
"""

import contextlib
import queue


class PoolTimeout(Exception):
    """No connection came free in time."""


class ConnectionPool:
    def __init__(self, connect, *, name="ledger-replica", size=4, acquire_timeout=2.0):
        self.name = name
        self.size = size
        self.acquire_timeout = acquire_timeout
        self._connect = connect
        self._idle = queue.LifoQueue()
        for _ in range(size):
            self._idle.put(None)  # A free slot, connected on first use.

    @property
    def in_use(self) -> int:
        return self.size - self._idle.qsize()

    def acquire(self):
        try:
            conn = self._idle.get(timeout=self.acquire_timeout)
        except queue.Empty as error:
            raise PoolTimeout(f"no connection free in pool {self.name!r} after {self.acquire_timeout}s") from error
        return conn if conn is not None else self._connect()

    def release(self, conn) -> None:
        self._idle.put(conn)

    @contextlib.contextmanager
    def connection(self):
        conn = self.acquire()
        try:
            yield conn
        finally:
            self.release(conn)
