# Customer erasure migration

The migration removes a customer's requested data from every live view of the
document store while keeping held evidence and unrelated records intact. It
reads the customer records in `data/` and writes the migration plan the storage
job executes:

```
python -m erasure.migrate --data data --output output/migration.json
```

All records are fictional. IDs, object names and keys are case-sensitive.

## Store and CDC cutover

`catalog.json` is `{watermark, cutover, at, nodes, heads}` (`watermark <= cutover`;
`at` is the policy/hold evaluation time). An immutable node is
`{id, object, parents, rows}`: `parents` is an ORDERED list of node IDs and row
keys are unique within a node. A row is a payload
`{key, deleted: false, tenant, alias, at, payload}` or a tombstone
`{key, deleted: true}`. Tombstones are never customer rows.

A node's original logical map overlays each parent's original map in parent
order, then its own rows; later occurrences of a key replace earlier ones
completely, tombstones included, so a tombstone stops an older value from coming
back. Parents are exact node IDs, not object heads. Missing parents or cycles
anywhere in the store are errors. Identical duplicate node definitions are
harmless; different definitions for one ID are an error. Keep every unrequested
payload field exactly.

`heads` maps objects to current node IDs (with the same `object`); snapshot heads
are validated before replay. `changes.json` is an unordered list of
`{seq, object, op, ...}`. Events with `seq > cutover` are ignored entirely.
Identical duplicate events are harmless; different events with the same
`seq <= cutover` are an error, even if covered. Only
`watermark < seq <= cutover` are replayed, in increasing `seq`:

* `put` with `value: node` adds the node and sets the object's head to it (objects must match);
* `head` with `node` sets the object's head to an existing node (objects must match);
* `delete` removes the object's head only; history stays in the store.

Covered events are not applied or validated beyond the duplicate rule. Invalid
references, object mismatches or conflicting definitions are errors. A put's
parent may arrive later in the cutover; the final store must be valid, and a
`head` event needs its node to exist at that point.

## Erasure requests and holds

`identity.json` rows `{tenant, alias, subject, from, until}` map aliases to
subjects over `[from, until)` (`until` null = open). Every original payload row
must resolve to exactly one subject for its tenant/alias at the row's own `at`;
no match or several distinct subjects is an error. Tenants are independent and
aliases can be recycled.

`requests.json` has unique `{id, tenant, subject, through}`. A payload row is
directly erased by every request with its tenant and subject and
`row.at <= through`. Later rows for that subject and rows of a recycled alias's
new subject are unaffected. Tombstones are never erased. An original node with
any directly erased own payload must not stay physically reachable from a live
head after the migration, even if an overlay currently hides that payload.

`holds.json` has unique `{id, node, from, until}`; a hold is active when
`from <= at < until` (null = open). An active hold on a missing node is an error;
inactive ones are ignored. An active hold retains its ORIGINAL node and every
original ancestor in isolated evidence storage (hold reads bypass rewrites).
This never lets held erased payloads stay live. Holding a parent does not retain
its descendants.

## Rewrite permissions and replacements

`policies.json` is an unordered list of policy deliveries
`{node, revision, known, effective_at, approved, allow, cost}`. Ignore deliveries
with `known > at`. Different visible deliveries for the same `(node, revision)`
are an error, even when unapproved or not yet effective. A node's current policy
is its highest APPROVED revision with `effective_at <= at`; unapproved drafts and
future revisions are not current authority. Every node has a current policy.
`allow: false` means the node may not be rewritten now; `cost` is the engineering
cost of rewriting it.

Rewriting a node creates ONE parentless clean snapshot of its ORIGINAL logical
map with ID `rewrite:<original>`. It keeps every original tombstone and every
unrequested payload unchanged, and replaces each directly erased payload with
exactly `{key, deleted: true}` (a deletion barrier, not an omitted key). Every
reference to a rewritten node (object heads and parent edges from other nodes) is
redirected to its clone. Nodes that are not rewritten keep their rows and
ordered parents. Clones always snapshot ORIGINAL content. Several heads may share
one clone. Rewriting does not change hold ancestry.

A plan is safe only when, for all live heads together, (1) no original node with
a directly erased own payload is reachable from a live head after redirects, and
(2) each head's effective view equals its ORIGINAL view with the requested rows
removed and every other current payload exactly retained (tombstones excluded
on both sides).

Choose, among safe plans that rewrite only currently allowed nodes, the lowest
total cost, then the fewest rewrites, then the lexicographically smallest
sorted list of original IDs. Zero rewrites is allowed. The plan purges every
original node that is neither reachable as a live original nor retained by an
active hold (including unreachable clean history). If no permitted safe plan
exists the command exits nonzero without writing.

At most 10 nodes, 4 parents per node, 8 own rows per node, 5 heads, 30 CDC
events, 40 policy deliveries, 8 requests/holds and 30 identity rows occur, so
searching all 2^10 rewrite subsets is fine.

## Migration file (`output/migration.json`)

```
{
  "current_heads": [{"object", "node"}],            # sorted by object, before redirects
  "erased_payloads": [{"node", "key", "requests"}],  # every directly erased own row, sorted by (node, key)
  "retained_for_hold": [{"node", "holds"}],          # active-hold ancestors, sorted by node
  "plan": {
    "cost": <int>,
    "rewrites": [{"original", "clone", "cost", "parents": [], "rows"}],  # by original; rows sorted by key incl. tombstones
    "live_roots": [{"object", "node"}],              # clone IDs for rewritten heads
    "live_originals": [...], "purge_nodes": [...],   # sorted original IDs
    "logical_views": [{"object", "rows"}]            # sorted by object; payload rows sorted by key
  }
}
```

Request and hold ID lists are sorted. The command writes atomically, creates
missing directories and exits nonzero, leaving an existing file untouched, on
any error.

## Repository rules

`README.md`, `pytest.ini`, `data/` and `production/` are customer records and
production state; do not modify them. Use only the Python standard library and
run the tests with `python -m pytest`.
