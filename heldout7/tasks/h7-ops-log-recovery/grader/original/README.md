# Marlow Quay checkpoint recovery service

Marlow Quay Provisions (fictional) lost its primary database. Its ledger, orders and stock shards were exported
as independently numbered transaction logs together with per-transaction decision seals. The `recovery`
package rebuilds a consistent checkpoint from that export: it buffers log evidence, then advances the
restored state to a target vector of log positions. `data/history.json` is the customer's actual export
and restore request. The format is an offline format defined here, not a PostgreSQL wire format.

Run the restore with:

    python -m recovery restore --history data/history.json --store state/recovery.db --output output/checkpoint.json

It initializes the store from the snapshot, ingests each export batch in order, advances to the requested
target and writes `{checkpoint_id, version, frontier, values, processed, order}` (the advance response plus
the checkpoint ID) atomically to the output. On any error it exits nonzero and leaves an existing output
untouched. Rerunning against the same store is safe: every call is an idempotent request replay.

## History file

`{checkpoint_id, snapshot, batches:[{request_id, expected_version, events, decisions}], restore:{request_id, expected_version, target}}`.
Batches may repeat an earlier batch exactly (the exporter retries deliveries).

## API and durable state

All functions accept a SQLite database pathname: `initialize(path, snapshot)`, `inspect(path)`,
`ingest(path, request_id, expected_version, batch)`, `advance(path, request_id, expected_version, target)`.
`initialize` is idempotent for an equal snapshot and rejects a different anchor. First initialization and equal
reinitialization return the CURRENT inspect-shaped summary without advancing version. `inspect` returns exactly
`{version, frontier, values, processed}`. A snapshot is `{frontier:{shard:LSN}, values:{shard:{key:string}}, applied:[committed_txid]}`;
`processed` initially maps these IDs to `"commit"`. Version starts at 0. Mutating calls return this summary plus
`ingested: true` or `order: [txids]` respectively. Every new accepted request, including an empty ingest or a no-op
advance, increments version once. Failed calls change nothing. All failures raise `ValueError` (message unconstrained).

Before the version check, an exact repeat of a request ID returns its original response, even after newer
requests or a restart. Reusing an ID with a different method, expected version or payload is an error. Payload
equality is JSON structural equality (object key order irrelevant). Mutations serialize across concurrent
processes (compare-and-swap on version). Database state, buffered evidence, processed transactions, request
identities and responses survive reopening.

## Evidence

`batch = {events:[event], decisions:[decision]}`. `event = {shard, lsn, txid, ordinal, key, before, after}`, where `lsn`
is a positive integer after that shard's ANCHOR frontier, `ordinal` a nonnegative integer global within its
transaction; `before`/`after` are a string or null (null means absent/delete). A repeated identical event at
(shard, lsn) is harmless; a conflicting one is an error for the whole batch. Evidence may arrive before its decision
and in arbitrary batches/order. Reject unknown shards, anchor (`applied`) transaction IDs, or coordinates at/before
the anchor. Already buffered historical evidence remains replayable after advancement.

`decision = {txid, outcome, parents, parts}`; outcome `commit` | `abort`, `parents` unique transaction IDs, `parts`
maps each touched shard to `{lsns:[strictly increasing positive coordinates], sha256}`. The digest is SHA-256 of the
UTF-8 JSON of the ENTIRE list of that transaction's events at those coordinates, in lsn order, using
`sort_keys=True, separators=(',', ':')`. Manifest ranges may interleave transactions. Empty parts/lsns, unknown shards,
anchor coordinates, invalid outcomes and conflicting decisions fail ingest. Identical decisions are harmless. At
ingest only syntax and conflicts are checked: missing seals/events, hashes, parents and closure are checked during
advance. Every transaction has 1..40 events with ordinals exactly 0..N-1 across all its shards. All buffered events
bearing its ID must appear exactly once in its seal; extra unsealed events invalidate it.

## Advancing to a target

The target has exactly the known shard keys and integer coordinates >= the current frontier. Every coordinate in each
(current, target] interval must have an event. Every selected transaction must be unprocessed and have a decision;
ALL its sealed events must lie in those intervals, including aborts. Do not repair a partial cut by silently
increasing another shard's coordinate. Every seal/hash/ordinal must validate, and no buffered event of that
transaction can be omitted. Each parent (a cross-shard dependency) must be a previously processed COMMIT or a selected
COMMIT; aborted/missing parents invalidate the cut.

Ordering edges connect distinct consecutive transaction IDs encountered in increasing lsn within each shard's
selected interval, plus parent→child edges. A cycle invalidates the cut. Repeatedly choose the lexicographically
smallest pending ID with no pending predecessor; return this deterministic order. Commit events execute in global
ordinal order and must match each key's before-image; then set `after`, deleting on null. Abort events consume their
log coordinates but neither check nor apply before/after. Only after ALL transactions validate and replay does the
whole target commit atomically; on any later failure earlier transactions roll back too. `processed` records commit
and abort decisions.

Bounds: <=8 shards, 400 events, 80 decisions, 40 events/transaction, 200 API calls. Input objects are not mutated.
IDs/keys are nonempty ASCII without colon; values strings or null. Except for the invalid cases described above,
inputs are well-shaped. Canonical JSON uses Python's default `ensure_ascii=True`. No network or dependencies.

## Repository rules

`README.md`, `data/`, `production/` and `pytest.ini` are customer records and configuration; do not edit them.
`production/restore_status.json` is updated by operations after review, never by the service. Implement the
`recovery/` package (helper modules welcome) and add or extend tests under `tests/`.
