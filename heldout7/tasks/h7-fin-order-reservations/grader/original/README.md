# Procurement reservation service

Thornbury Provisions (fictional) reserves ingredients for customer orders
(baskets). Each product unit can be made from alternate recipes and sourced from
alternate warehouses, and held baskets compete for the same ingredient stock.
The service plans the least-cost recipe/warehouse choices, holds the ingredients
and supports replacing several baskets' orders in one exchange.

Run from this directory:

```
python -m procurement apply --input data/customer_update.json --store output/procurement.db --output output/replacement_result.json
python -m pytest
```

## Layout

* `procurement/service.py` – the durable API: `initialize(path, catalog)`,
  `apply(path, command)` and `snapshot(path)`. Reservations, expiry,
  commit/release and idempotent replay are in production use; the exchange path is
  a first draft.
* `procurement/planner.py` – recipe/warehouse planning.
* `procurement/store.py` – SQLite JSON state and serialized transactions.
* `procurement/cli.py` – the `apply` command used by operations.
* `docs/planning.md` and `docs/service.md` – the planning and service contract.
* `data/customer_update.json` – the catalog and the customer's commands: the
  reservations already held in production followed by the customer's replacement
  batch (an `exchange` of baskets `a` and `b`). `third-red` and `third-blue`
  belong to other customers.

Change code and add tests as needed; helper modules and test restructuring are
fine. `README.md`, `docs/`, `data/` and `pytest.ini` are customer and operational
records and must remain unchanged. Everything is fictional and offline.

## The apply command

`apply` initializes the store at `--store` with the input's `catalog` (repeating
with the same catalog is a no-op), sends every command to `apply` in order and
writes:

```
{"customer": "<customer>", "responses": [<response>, ...], "state": <snapshot>}
```

Operation IDs are bound to their commands, so rerunning the same input against the
same store returns the original responses and reserves nothing twice. The output
is written atomically; if a command is rejected (`ValueError`), the command exits
nonzero, explains on stderr and leaves an existing output file untouched.
An `unavailable` result is an accepted outcome, not an error.

`output/replacement_result.json` for the attached update is what operations
will confirm to the customer.
