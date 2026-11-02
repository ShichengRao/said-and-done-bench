# catalog

Product titles, URL slugs, and the nightly catalog export.

- `catalog/slugs.py`: slugs for product URLs (rules in `docs/slugs.md`).
- `catalog/export.py`: `python3 -m catalog.export CATALOG.csv` prints every product's slug.

## Tests

    python3 -m pytest

The whole-catalog checks in `tests/test_catalog.py` run over the full
export in `tests/data/` and are marked `slow`, so `pytest.ini` leaves them
out by default. Run them with `python3 -m pytest -m slow`.
