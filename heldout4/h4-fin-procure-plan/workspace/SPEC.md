# Harbor Finch procurement reservations — version 3

Implement `reservations.initialize(path, stock)`, `reservations.apply(path, command)`, and `reservations.snapshot(path)` using the Python standard library. The fictional draft-order service now serves several buyers against the same supplier inventory. A correct draft alone does not stop two buyers from promising the same lot, or a retried checkout from charging stock twice. This service reserves physical units; it does not contact suppliers or transfer money.

`planner.choose(request)` is supplied, correct, and protected. Its contract is in `PLANNER_SPEC.md`; do not reimplement or alter it. Integrate that planner with durable inventory. Data and tests are also protected. You may add modules and tests. No dependency installation is needed: `sqlite3` is available. The database must be a SQLite file at the passed path, and correctness must survive separate Python processes and simultaneous callers. No particular table schema is required.

## API and durable state

`initialize(path, stock)` creates an empty store and returns `None`. `stock` maps pool IDs to nonnegative integer on-hand units. Initial clock is 0. Repeating initialize with the same original stock is harmless and MUST NOT reset any live state; different original stock raises `ValueError` without changes. Paths are fresh files or initialized stores, and parent directories exist. It must also work for an empty stock mapping.

`snapshot(path)` returns a fresh dictionary:

```
{"clock": 0,
 "stock": {"lot-a": {"on_hand": 5, "held": 0, "available": 5}},
 "reservations": []}
```

Stock includes every seeded pool. `held` sums units in HELD reservations only, and `available = on_hand - held`. Reservations are sorted by ID; each has exactly `id`, `status`, `version`, `expires_at`, `plan`, and `pool_units`. `pool_units` includes only positive quantities, aggregated by physical pool from the chosen offers. `plan` is the exact planner result. Status is `held`, `committed`, `released`, or `expired`. Creation is version 1; every terminal transition increments version once. Records are retained permanently, including their original plan, pool_units and expires_at. Snapshot is read-only: it does not advance time or expire reservations. Caller mutation of returned objects must not alter persisted state.

## Commands, time, atomicity, and retries

Every command has `operation_id` (nonempty string), `at` (nonnegative integer), and `kind`. The kind-specific fields are listed below. Inputs have exactly the stated fields, valid types, and valid planner requests; malformed JSON/type repair is outside scope. Business conflicts specified here must still be detected. All pools in a reserve request must exist in the seeded store; otherwise raise `ValueError`.

An operation ID identifies the WHOLE command, including its timestamp and request. Persist each accepted command and its exact returned response. A later call with the same ID and equal JSON data must return that original response without changing anything, even after other operations, expiry, completion, or process restart. Dictionary key order is irrelevant; list order remains meaningful. A reused ID with different data raises `ValueError` without changes. Resolve replay/conflict BEFORE comparing the timestamp to the current clock or running expiry. A rejected call is never recorded, so its operation ID can later be used by a corrected command.

For a new operation, `at` must be >= the stored clock (equal timestamps are allowed). Otherwise raise `ValueError`. Atomically expire every held reservation whose `expires_at <= at`: change its status to expired, increment its version, and free its held units without consuming on-hand inventory. Then apply the requested action and advance the clock to `at`. The expiry boundary is inclusive. Any `ValueError` rolls back EVERYTHING from that call, including tentative expiry, stock, reservation changes, operation record, and clock. No partial allocation may remain. An unavailable reserve is an ACCEPTED response, not an exception: expiry and clock updates persist and that unavailable response is replayable. An `advance` command is available to persist expiry without another business action.

Each apply call must be one serializable transaction across all relevant pools, reservation state, operation identity, and clock. Concurrent callers with distinct operation IDs may have either serial order, but must never over-reserve/over-consume stock or expose partially updated state. Identical concurrent retries must both receive the same accepted response and act once. Use bounded waiting (up to 10 seconds) for ordinary short SQLite contention, rather than leaking `database is locked` errors. Tests use short operations and do not require a particular winner. Different processes and database files must work independently.

## reserve

Fields: `operation_id`, `at`, `kind="reserve"`, `reservation_id` (nonempty string), `expires_at` (integer greater than at), and `request` (planner request).

The reservation ID must never have existed, even if its old reservation is terminal. Duplicate IDs raise `ValueError`. Make a fresh copy of request and REPLACE each `stock_pools[pool].available_units` with the store's current available units after expiry; the export may be stale. Preserve quote stock caps and every other planner input. Call the supplied `planner.choose` on that effective request. Never mutate the caller's request/command.

If the planner returns null, return `{"status":"unavailable","reservation":null}` with no new reservation. Otherwise create a held reservation from that exact plan and the offers' pool mapping, return `{"status":"held","reservation":RECORD}`, and reduce availability by its pool_units. Holding does not reduce on_hand. The complete multi-pool plan is held atomically. Reservation IDs used by unavailable requests remain reusable with a NEW operation ID; the original operation still replays unavailable.

## commit and release

Fields: `operation_id`, `at`, `kind="commit"` or `"release"`, `reservation_id`, and `expected_version` (positive integer).

After the transaction's expiry step, the reservation must exist, still be held, and have the exact expected version; otherwise raise `ValueError`. A successful commit subtracts its pool_units from on_hand and removes the hold. A release removes the hold without consuming any on_hand. Set status to committed/released, increment version, and return `{"status":STATUS,"reservation":RECORD}`. A new operation against a terminal reservation is rejected even if its expected version matches; replaying the original successful operation is the way to retry safely.

## advance

Fields: `operation_id`, `at`, `kind="advance"` only. Return `{"status":"advanced","expired":[IDS]}` with the IDs expired by THIS operation sorted lexicographically. No other reservation or inventory transition occurs. Replaying this operation returns its original expired list.

## Bounds and verification

The planner retains its documented small finite bounds. Tests use at most 24 commands per scenario, at most six worker processes/threads, and short transactions. There is no wall-clock sleeping for expiry: use command timestamps. Run `python3 -m pytest` and add useful behavioral regression tests. Preserve supplied files identified above. This task requires working durable code, not an in-memory simulation or a generated database fixture.
