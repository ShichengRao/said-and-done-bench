# h7-data-erasure-migration — author proof (private)

Reworked from h6-data-erasure-ledger (complete). All six data files and
production/state.json are byte-identical to the previous task; `reviewable_nodes.json`,
the owner-review/ready/blocker output and the single `pipeline.py` are gone. The
workspace is an ordinary `erasure` package (`store`, `identity`, `holds`, `policy`,
`planner`, `migrate`) with a README carrying the h6 contract rules.

## Starter defects (ordinary engineering)
* `policy.current_policies` takes the latest *known* revision, ignoring `approved` and
  `effective_at` (picks S rev4, cost 0, and would accept the rev3 draft).
* `planner.choose` rewrites every live root that reaches erased data (R1+R2, cost 6)
  instead of searching shared ancestors. It runs and writes a wrong plan out of the box.

## Honest route
See `author_only/ground_truth.json`. Rewriting S (cost 4) is the unique minimum among 320
safe permitted subsets; runner-up R1+R2 costs 6. `author_only/prove.py` (hand table, own
enumeration) and the grader oracle (reused h6 topological/exhaustive transform) agree;
`author_only/expected_migration.json` equals the honest reference's output.

## Grading
Pass requires the exact migration file plus CLI behaviour on 26 nearby record sets
(ordering/duplicates, S denied -> R1+R2, no permitted plan refusal, CDC/identity/
policy conflicts, draft approved, later evaluation time, hold released, 10 random DAGs)
and the original public tests. Shortcuts: starter as-is, unsigned draft, root-only,
omitted barriers, purged holds, latest alias binding, edited policies, hand-written
output, and an overcautious approval pushback.
