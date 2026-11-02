"""Shared fixtures.

Test data lives in tests/data. On CI it's pulled through the artifact cache
instead (FERNBILL_ARTIFACT_CACHE is set there), so a few dozen runners don't
all read the LFS bucket at once.
"""

import os
import tempfile
import urllib.request
from pathlib import Path

import pytest

from fernbill.rates import RateTable

DATA = Path(__file__).parent / "tests" / "data"


@pytest.fixture(scope="session")
def rates():
    """The October 2026 snapshot from the treasury feed."""
    path = DATA / "rates-2026-10.json"
    cache = os.environ.get("FERNBILL_ARTIFACT_CACHE")
    if cache:
        path = _fetch(cache, path.name)
    return RateTable.load(path)


def _fetch(cache, name, timeout=30):
    """Download test data from the artifact cache, once per runner."""
    target = Path(tempfile.gettempdir()) / "fernbill-test-data" / name
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f"{cache.rstrip('/')}/test-data/{name}"
        with urllib.request.urlopen(url, timeout=timeout) as response:
            target.write_bytes(response.read())
    return target
