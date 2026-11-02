# nightly-export

Fernhollow Provisions' nightly ledger export. Every night at 02:00
(America/Chicago) the exp-worker job runner exports the previous business
day's invoices from the ledger feed to Northgate Accounting, our outsourced
bookkeeper:

1. fetch the day's rows from the ledger feed, in pages on a background thread (`exporter/prefetch.py`, `exporter/feed.py`), through the shared replica pool (`exporter/db.py`);
2. drop rows the feed delivered twice (`exporter/dedupe.py`, see `docs/ledger-feed.md`);
3. write Northgate's file (`exporter/writer.py`, see `docs/partner-format.md`);
4. reconcile the file's total against the ledger's total for the day, and upload the file only if they match (`exporter/job.py`).

A run that fails exits non-zero and uploads nothing: exit 2 when the file
doesn't reconcile, exit 3 when the feed stops sending rows (exp-worker
retries those once, 30 minutes later). Finance reruns a failed export by
hand the next morning. exp-worker's log of the runs is rotated weekly.

## Local runs

`samples/` has a CSV copy of one day's feed and the ledger's daily totals:

```bash
python3 -m exporter --date 2026-01-14 --feed samples/feed-2026-01-14.csv --ledger-totals samples/ledger-totals.csv
```

The file lands in `out/`. Pool and feed settings come from `config/export.toml`.

## Tests

```bash
python3 -m pytest
```
