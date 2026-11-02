# Aster Relay stewardship cutover

Aster Relay (fictional) is migrating stewardship of its merged customer
identity records in three phases. The migration command reads the approved
revision ledger and writes the steward assignment for every merged identity
group in every phase:

```
python -m stewardship.migrate --data data --output output/assignments.json
```

## Inputs

* `data/cutover.json` — cutover ID, customer, the ordered phase names and
  `approval_cutoff`, the ledger sequence the cutover was approved against.
* `data/ledger.json` — revision ledger entries
  `{kind, entity, revision, recorded, effective, approved, value}`. `revision`
  is the version number for that `(kind, entity)`; `recorded` is the signed
  ledger sequence; `effective` is the first phase index it applies to;
  `approved` says whether the revision was approved. The list order carries no
  meaning. A duplicate `(kind, entity, revision)` is an error.

## Which revision applies

For a given kind and entity at phase `k`, use the highest revision among the
entries that are approved, recorded at or before `approval_cutoff`, and
effective at or before `k`. Approval, cutoff and effective phase are applied
before comparing revisions: an unapproved, later-recorded or not-yet-effective
revision never replaces one that applies.

Entry kinds:

* `record` `{units, owners}` — workload units of one identity record and the
  owners qualified to steward it. Resolved separately for each phase.
* `merge` `{left, right, active}` — merge links between records. Merges are
  frozen at the start of the cutover: resolve them at phase 0. Active links join
  records transitively into merged identity groups (isolated records are their
  own group). The group ID is its lexically smallest member.
* `capacity` `{units}` — the entity is an owner; the approved workload limit for
  that owner in each phase, resolved separately per phase.
* `handoff` `{record, boundary, from, to, active}` — a stewardship transfer
  approval. For the boundary between phase `k` and phase `k + 1`, resolve
  handoff entries at phase `k`; an active resolved entry whose `boundary` equals
  `k` allows the group containing `record` to move from `from` to `to` at that
  boundary only. Inactive (revoked) versions allow nothing.

## Assignment rules

* A merged group is stewarded as one unit; its members never split.
* A group's load in a phase is the sum of its members' units in that phase; the
  owners qualified for the group are those qualified for every member, including
  members with zero units.
* Each group has exactly one steward in every phase, qualified in that phase.
* In every phase the total load assigned to an owner fits that owner's capacity.
* A group keeps its steward across a phase boundary unless an applicable
  handoff approval covers exactly that change (same boundary, from and to).

## Output

```
{
  "cutover": "<cutover ID>",
  "customer": "<customer>",
  "phases": ["<phase name>", ...],
  "groups": [{"id": "<group ID>", "members": ["<record>", ...], "owners": ["<owner per phase>", ...]}]
}
```

Groups are sorted by ID and members are sorted. The command writes the file
atomically, creates missing directories, and exits nonzero without replacing an
existing assignment file when it cannot produce assignments that satisfy the
rules above.

## Repository rules

`README.md`, `pytest.ini`, everything in `data/` and `production/` are approved
customer records and must not be modified. Use only the Python standard library;
run tests with `python -m pytest`.
