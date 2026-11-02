# catalog_sync

Each night, today's prices and stock levels for every product we sell from
Halden Wholesale, for the storefront. Cron runs `python3 -m catalog_sync run`
at 02:00, when Halden publishes the day's prices; it fetches each SKU in
`data/skus.txt` from Halden's API (`docs/supplier-api.md`) and writes
`out/catalog.jsonl`, which the storefront rebuild reads at 02:30. Each
night's output (the sync's and the rebuild's) is in `logs/`.

## Trying it out

`python3 -m catalog_sync.fake_supplier` runs a stand-in for Halden's API on
port 8099 that answers like the real one, and about as slowly. With it
running:

    CATALOG_SUPPLIER_URL=http://127.0.0.1:8099/v3 python3 -m catalog_sync run --limit 50

## Tests

    python3 -m pytest
