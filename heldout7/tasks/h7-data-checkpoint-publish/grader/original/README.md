# Aster Relay migration checkpoint publisher

Aster Relay (fictional) migrates a customer's records from three exported shard
logs. The publisher reads the export in `data/`, finds the greatest causally
consistent checkpoint, replays it onto the base snapshot and writes the
checkpoint the migration job loads:

```
python -m checkpoint.publish --data data --output output/checkpoint.json
```

## Export files

Shard, tenant, customer, alias and transaction IDs are case-sensitive strings.
Lists are unordered except transaction operations. Unless listed as an error
below, records follow these shapes and reference valid IDs.

* `snapshot.json` — `{cut: {shard: offset}, customers: [...], aliases: [...]}`.
  A customer is `{tenant, id, seats, tier, active, ...}` (seats a nonnegative
  integer; keep every other attribute). Customer keys `(tenant, id)` and alias
  keys `(tenant, alias)` are unique; an alias `{tenant, alias, customer}` points
  to an existing customer of that tenant.
* `request.json` — `{upper: {shard: offset}, minimum: {shard: offset}}` with the
  snapshot's shard keys and `snapshot.cut <= minimum <= upper` per shard.
* `transactions.json` — `{id, order, decision, parts, depends, operations}`.
  IDs and integer orders are unique (a duplicate ID is an error). `decision` is
  `commit`, `abort` or `unresolved` (coordinator decision not yet known). A part
  `{shard, first, last}` occupies every offset in that inclusive range, strictly
  after the snapshot cut; at most one part per shard, and transactions never
  overlap within a shard. `depends` lists transactions with smaller order. The
  manifest may describe transactions above `upper`.
* `deliveries.json` — `{shard, offset, transaction}` rows for exported log
  records. A row must name the one transaction whose part covers that
  shard/offset, otherwise it is an error. Identical repeated rows are harmless;
  different rows for the same `(shard, offset)` are an error. All rows are
  validated, including rows above `upper`. A missing row means that offset was
  not exported; it is not an implicit no-op.

At most three shards, six transactions, five offsets above the base per shard,
three parts per transaction, six operations per transaction, eight customers and
eight initial aliases.

## Consistent checkpoint

For each shard the export reaches the end of the contiguous delivered prefix
right after `snapshot.cut`, capped at `upper`; a delivery past a gap does not
fill the gap.

A candidate checkpoint gives each shard an offset between `snapshot.cut` and
that reach. It includes a transaction only if every offset of every part is at
or below its shard's offset, and excludes it only if none is; a partially
covered transaction (including a partially exported abort) makes the checkpoint
invalid. An `unresolved` transaction can never be included. Every dependency of
an included transaction must be included too (an included abort satisfies a
dependency but applies nothing).

Publish the componentwise greatest valid checkpoint: it is at or above every
other valid checkpoint on every shard (it always exists; the base cut is
valid). Dropping a transaction can pull other shards and dependent
transactions back in turn. The requested `minimum` is the lowest checkpoint the
customer accepts on each shard; if the greatest valid checkpoint is below it on
any shard, the publisher exits nonzero without writing.

## Replay

Start from the snapshot customers and aliases. Replay the included `commit`
transactions in increasing order, operations in list order. Aborted and
excluded transactions apply nothing (their operations are not validated).
Binding changes are visible to later operations and transactions.

* `{kind: bind, tenant, alias, customer}` sets the binding; an unknown customer is an error.
* `{kind: unbind, tenant, alias}` removes it if present.
* `{kind: adjust, tenant, alias, delta}` adds `delta` to the bound customer's
  seats; a missing binding or negative seats is an error.
* `{kind: tier, tenant, alias, value}` sets the bound customer's tier; a missing binding is an error.
* `{kind: close, tenant, alias}` sets the bound customer's `active` to false; a missing binding is an error.

## Checkpoint file (`output/checkpoint.json`)

```
{
  "cut": {"<shard>": <offset>},
  "included": ["<transaction>", ...],
  "applied": ["<transaction>", ...],
  "deferred": ["<transaction>", ...],
  "customers": [...],
  "aliases": [{"tenant": ..., "alias": ..., "customer": ...}]
}
```

`included` lists the finalized transactions in the checkpoint in order,
`applied` only its committed ones, `deferred` every other transaction ID sorted.
Customers are sorted by `(tenant, id)` and keep every original customer; aliases
are sorted by `(tenant, alias)`. Any error fails the whole run: the publisher
exits nonzero and leaves an existing checkpoint untouched. It writes atomically
and creates missing directories.

## Repository rules

`README.md`, `pytest.ini`, `data/` and `production/` are the customer's export
and production state; do not modify them. Use only the Python standard library
and run the tests with `python -m pytest`.
