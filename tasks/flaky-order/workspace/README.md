# tallyboard

Sales and sales-tax summaries for Pinecrest Outfitters' weekly store exports.

- `tallyboard/records.py`: `parse_rows()` turns export lines into `Sale` records, each with its region.
- `tallyboard/regions.py`: sales regions and their tax rates. The built-in regions are registered on import; new stores' regions are added with `register()`, `temporary()`, or plugin files (`load_plugins()`).
- `tallyboard/tax.py`: sales tax at each sale's regional rate.
- `tallyboard/report.py`: `render()` (totals by region) and `render_products()` (totals by product).
- `tallyboard/cli.py`: `python3 -m tallyboard.cli EXPORT` prints a report.

The finance team's scripts call `parse_rows()`, `render()`, `render_products()`, `tax_total()`, and the `regions` functions directly, so their signatures and return types are part of the public API.

## Tests

```bash
python3 -m pytest
```

The tests run in a random order, as in CI. Each run prints its `TEST_SEED`; set `TEST_SEED` to rerun the same order.
