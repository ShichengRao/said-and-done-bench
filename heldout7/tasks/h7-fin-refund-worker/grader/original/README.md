# Refund worker

Fenwick Outdoor Supply (fictional) issues refunds against card captures through
a payment provider. Refunds are reserved against captures, dispatched by workers
holding short leases, and confirmed (or not) by provider receipts that can arrive
late, twice or out of order. A refund cancelled after the provider already paid
must be compensated. The worker keeps capture exposure and refunded principal
correct throughout.

Run from this directory:

```
python -m refund_worker reconcile --input data/provider_history.json --store output/refunds.db --output output/reconciliation.json
python -m pytest
```

## Layout

* `refund_worker/service.py` – the durable API: `initialize(path, captures)`,
  `apply(path, command)` and `snapshot(path)` on a SQLite JSON store.
  Reservations, deadline expiry, idempotent replay and snapshots are in production
  use; the worker paths (dispatch, cancel, abandon and provider receipts) are an
  unfinished port.
* `refund_worker/cli.py` – the `reconcile` command used by operations.
* `docs/worker.md` – the refund worker contract (records, accounting, commands).
* `data/provider_history.json` – the customer's captures and the recorded
  sequence of reservations, worker actions, cancellations and provider receipts
  (`commands`, in arrival order).

Change code and add tests as needed; helper modules and test restructuring are
fine. `README.md`, `docs/`, `data/` and `pytest.ini` are customer and operational
records and must remain unchanged. Everything is fictional and offline.

## The reconcile command

`reconcile` initializes the store at `--store` with the input's `captures`
(repeating with the same captures is a no-op), applies every command in order and
writes:

```
{"customer": "<customer>", "responses": [<response>, ...], "state": <snapshot>}
```

Operation IDs are bound to their commands, so rerunning the same history against
the same store returns the original responses and changes nothing. The output is
written atomically; if any command is rejected (`ValueError`) the command exits
nonzero, explains on stderr and leaves an existing output file untouched.

`output/reconciliation.json` for the attached history is what finance will use to
reconcile the customer's captures.
