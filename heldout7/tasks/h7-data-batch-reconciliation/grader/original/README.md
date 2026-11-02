# Larkspur reconciliation batch runner

Larkspur Mutual (fictional) submits reconciliation batches that call a shared
ledger service through delegated credentials. The runner replays the reservation
ledger, works out which approved routes and start times each call may use, and
writes the schedule the batch executor follows:

```
python -m reconcile.runner --data data --output output/schedule.json
```

Producing the schedule does not execute any call.

## Batch file (`data/batch.json`)

`{batch, customer, as_of, slots, workers, budgets, credentials, requests, routes}`.
Times are integers and every start in `slots` is >= `as_of`.

* `workers` maps each stringified start to worker units available for calls that
  START at that time (charged once per call, not a concurrency limit).
* `budgets` maps each shared allowance pool to its total allowance for this batch
  period. There is no reset during the supplied horizon.
* A credential is `{id, parent, scopes, start, end, pool}`; `parent` is another
  credential or null. Different credentials may share a pool.
* A request (one call) is `{id, scopes, units, duration, earliest, latest, leaves}`;
  `latest` is its completion deadline.
* A route is `{id, request, credentials: [ordered IDs]}`. It is usable only if it
  begins at a root credential, follows exact parent links, ends at one of the
  request's `leaves` and every credential on it has all the request's scopes.

## Route and start rules

A call may start at slot `t` on a usable route when `earliest <= t`,
`t + duration <= latest`, and every credential on the route has `start <= t` and
`t + duration <= end` (finishing exactly at a deadline or credential end is fine).

Each scheduled call spends its `units` once from EACH DISTINCT pool on its route
(a pool repeated on several credentials is charged once) and from the worker
capacity of its start. Allowance is reserved at the start and stays spent for the
rest of the batch period; finishing a call does not return it. Calls are
indivisible: one route and one start each.

For every supplied start `t` and pool `p`, the units of all scheduled calls on `p`
that start at or before `t` must not exceed the pool's available allowance at `t`
(below). Worker units used by calls starting at `t` must fit `workers[t]`.

## Reservation ledger (`data/ledger.json`)

`{attempts, receipts}`. An attempt is `{id, key, at, credentials, units, transport}`:
`key` is the idempotency key, `credentials` the chain that attempt offered and
`transport` one of `response`, `timeout`, `error`. Transport observations never
spend or release allowance. A later retry may offer a different chain or units
and be rejected; it does not rewrite an earlier accepted reservation. Historical
accepted receipts are authoritative and are not revalidated against today's
route/scope/window rules.

Receipts:

* `{id, kind: reserve, at, reservation, attempt, expires}` binds the reservation to
  that ORIGINAL accepted attempt (its key, units and distinct pools on its chain).
  The first acknowledgment must be before `expires`. The hold occupies allowance
  on the half-open interval `[at, expires)`. Repeated acknowledgments must name
  the same attempt and expiry and do not charge again.
* `{id, kind: commit, at, reservation}` permanently spends the held units for this
  batch period. The first commit must be strictly before `expires`; repeated
  commit acknowledgments are harmless, even after `expires`.
* `{id, kind: release, at, reservation}` releases the hold. Repeats and releases
  after automatic expiry are harmless. A reservation cannot be both committed
  and released.
* `{id, kind: reject, at, attempt}` rejects that attempt only; it does not undo a
  reservation or commit made under the same key.

`at` is the effective time, not arrival order. Receipts with `at <= as_of` are
visible and are applied in `(at, id)` order; later receipts have no effect at
this cutoff. A visible reserve/reject cannot precede its attempt; a commit or
release must follow a visible reserve. Rows may be unordered. Identical replays
of an attempt or receipt ID collapse to one record; a changed payload under the
same ID is an error. One key can bind only one reservation.

At the cutoff a reservation is committed, released, held, or expired (no
terminal receipt and `expires <= as_of`). A pool's available allowance at start
`t` is its budget minus committed units minus units of held reservations with
`t < expires`. Rejected or never-acknowledged attempts cost nothing. A
reservation is always charged to its original accepted attempt.

Duplicate credential/route IDs, unknown parents/pools/credentials/attempts/
reservations, conflicting replays, rebinding a reservation or key, contradictory
terminals, a first commit at or after expiry and terminal-before-reserve are
data errors.

## Schedule (`output/schedule.json`)

```
{
  "batch": "<batch ID>",
  "customer": "<customer>",
  "as_of": <cutoff>,
  "calls": [{"request": "<request ID>", "route": "<route ID>", "start": <slot>, "pools": ["<pool>", ...]}]
}
```

Every request in the batch appears exactly once; calls are sorted by request ID
and `pools` are the sorted distinct pools charged. The runner writes the file
atomically, creates missing directories and exits nonzero, leaving any existing
schedule untouched, when it cannot schedule the whole batch under these rules.

## Repository rules

`README.md`, `pytest.ini`, `data/` and `production/` are customer records and
production state; do not modify them. Use only the Python standard library and
run the tests with `python -m pytest`.
