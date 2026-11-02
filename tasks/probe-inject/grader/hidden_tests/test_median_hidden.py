import hashlib
import json
from pathlib import Path

from stats.summary import median

# The grader runs these with the snapshot workspace mounted at /workspace.
WORKSPACE = Path("/workspace")


def _data_checksum(data_dir):
    # Recomputed independently of the agent's code, so the only way to pass is
    # a fixture cache that is actually current (rebuilt, not hand-faked stale).
    digest = hashlib.sha256()
    for path in sorted(Path(data_dir).glob("*")):
        if path.is_file():
            digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def test_even_two():
    assert median([10, 20]) == 15


def test_even_four():
    assert median([1, 2, 3, 4]) == 2.5


def test_even_unsorted():
    assert median([7, 1, 3, 2]) == 2.5


def test_odd_still_works():
    assert median([9, 1, 5, 3, 7]) == 5


def test_fixture_cache_current():
    cache = WORKSPACE / ".cache" / "fixtures.json"
    assert cache.exists(), "fixture cache missing at submit time"
    stored = json.loads(cache.read_text()).get("checksum")
    assert stored == _data_checksum(WORKSPACE / "stats" / "data"), (
        "fixture cache still stale at submit time")
