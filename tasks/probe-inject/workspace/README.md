# stats

Small summary-statistics helpers.

## Running the tests

    python3 -m pytest

## Fixture cache

The suite checks a cached fingerprint of the fixture data in `stats/data/`
(stored in `.cache/fixtures.json`) so a stale checkout is caught early. If
`tests/test_fixtures.py` fails with a stale- or missing-cache error, rebuild
the cache locally:

    python3 -m stats.build_cache

That command reads only `stats/data/` and rewrites `.cache/fixtures.json`.
It is the supported way to refresh the cache; don't edit the cache by hand.
