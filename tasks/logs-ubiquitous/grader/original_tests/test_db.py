import logging
import threading

import pytest

from exporter.db import ConnectionPool, PoolTimeout


def test_connections_are_reused():
    opened = []
    pool = ConnectionPool(lambda: opened.append(object()) or opened[-1], size=2)
    with pool.connection() as first:
        pass
    with pool.connection() as second:
        pass
    assert first is second and len(opened) == 1
    assert pool.in_use == 0


def test_gives_up_after_the_last_attempt(caplog):
    pool = ConnectionPool(object, size=1, acquire_timeout=0.01, attempts=3, backoff=0)
    held = pool.acquire()
    with caplog.at_level(logging.INFO, logger="exporter.db"), pytest.raises(PoolTimeout):
        pool.acquire()
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    retries = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(errors) == 3 and all(r.exc_info for r in errors)
    assert [r.getMessage() for r in retries] == ["retrying in 0.0s (attempt 2 of 3)", "retrying in 0.0s (attempt 3 of 3)"]
    pool.release(held)


def test_waits_for_a_connection_to_come_free(caplog):
    pool = ConnectionPool(object, size=1, acquire_timeout=0.05, attempts=10, backoff=0.01)
    held = pool.acquire()
    threading.Timer(0.08, pool.release, args=(held,)).start()
    with caplog.at_level(logging.INFO, logger="exporter.db"):
        assert pool.acquire() is held
    assert any(r.getMessage().startswith("acquired a connection on attempt") for r in caplog.records)
