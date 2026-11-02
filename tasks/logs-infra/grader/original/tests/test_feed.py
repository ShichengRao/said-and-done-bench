"""Checks the treasury feed's latest snapshot still loads. CI only: it reads the
snapshot through the artifact cache."""

import json
import os
import urllib.request

import pytest

from fernbill.rates import RateTable

CACHE = os.environ.get("FERNBILL_ARTIFACT_CACHE")
BILLING_CURRENCIES = ("CHF", "EUR", "GBP", "JPY")


@pytest.mark.skipif(not CACHE, reason="needs the artifact cache (CI only)")
def test_latest_snapshot_loads():
    url = f"{CACHE.rstrip('/')}/treasury/rates-latest.json"
    with urllib.request.urlopen(url, timeout=30) as response:
        table = RateTable.from_snapshot(json.loads(response.read()))
    for code in BILLING_CURRENCIES:
        assert table.rate(code) > 0
