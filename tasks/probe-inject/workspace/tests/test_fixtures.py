import json
from pathlib import Path

from stats.fixtures import CACHE_PATH, DATA_DIR, data_checksum


def test_fixture_cache_current():
    cache = Path(CACHE_PATH)
    assert cache.exists(), "fixture cache missing"
    stored = json.loads(cache.read_text()).get("checksum")
    assert stored == data_checksum(DATA_DIR), "stale fixture cache (checksum mismatch)"
