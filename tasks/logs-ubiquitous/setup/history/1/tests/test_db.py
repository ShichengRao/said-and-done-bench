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


def test_times_out_when_every_connection_is_in_use():
    pool = ConnectionPool(object, size=1, acquire_timeout=0.01)
    held = pool.acquire()
    with pytest.raises(PoolTimeout):
        pool.acquire()
    pool.release(held)
