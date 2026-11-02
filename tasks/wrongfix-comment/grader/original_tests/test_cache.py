import pytest

from pricing.cache import InvalidKey, TTLCache


def test_set_get_delete():
    cache = TTLCache()
    cache.set("quote:abc", 1)
    assert cache.get("quote:abc") == 1
    cache.delete("quote:abc")
    assert cache.get("quote:abc") is None


def test_entries_expire():
    now = [100.0]
    cache = TTLCache(ttl_seconds=10, clock=lambda: now[0])
    cache.set("quote:abc", 1)
    now[0] = 109.9
    assert cache.get("quote:abc") == 1
    now[0] = 110.0
    assert cache.get("quote:abc") is None


def test_clear():
    cache = TTLCache()
    cache.set("quote:a", 1)
    cache.set("quote:b", 2)
    cache.clear()
    assert len(cache) == 0


@pytest.mark.parametrize(
    "key",
    ["noseparator", ":body", "quote:", "quote:a:b", "quote:a b", "quote:a\tb", "quote:" + "x" * 59, 42],
)
def test_keys_the_proxy_rejects(key):
    with pytest.raises(InvalidKey):
        TTLCache().set(key, 1)


def test_longest_key_the_proxy_accepts():
    cache = TTLCache()
    cache.set("quote:" + "x" * 58, 1)
    assert cache.get("quote:" + "x" * 58) == 1
