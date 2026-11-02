"""Fixture-cache helpers.

The test suite checks a small cached fingerprint of the fixture data under
`stats/data/` against the live files, so a stale checkout is caught before the
real tests run. Rebuild the cache with `python3 -m stats.build_cache` (see the
README); never edit the cache by hand.
"""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "stats" / "data"
CACHE_PATH = ROOT / ".cache" / "fixtures.json"


def data_checksum(data_dir=DATA_DIR):
    """A stable fingerprint of every file under the fixture data directory."""
    digest = hashlib.sha256()
    for path in sorted(Path(data_dir).glob("*")):
        if path.is_file():
            digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()
