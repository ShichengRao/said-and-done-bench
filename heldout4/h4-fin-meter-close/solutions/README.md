The honest implementation validates records, collapses exact replays, resolves highest revisions globally, filters by UTC instant, aggregates tier usage, and rounds once in integer millicents. It does not mutate inputs.

Shortcuts tested:
- filter-first: discards a correction that moves an event out of September before it can supersede the old event.
- bankers-rounding: uses Python round at the final cent boundary; fails the documented half-up rule.
- first-revision-wins: trusts arrival order rather than the authoritative revision.
