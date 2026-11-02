# Backup v2 schema clarification

This revision makes two existing output shapes explicit: unique_symbols always has exactly width entries, with a null at each unresolved position (all null when there are no candidates); owner_plan.queries is a sorted list of query-ID strings. It also names the concrete fragment-recovery/owner-reread workflow in task metadata.

The production data, recovery algebra, reference implementations, graders, independent oracle, owner interventions and external tests are unchanged. Only the workspace contract and its trusted original copy change the grader hash. This is a fairness/schema clarification, NOT substantive additional difficulty. No run is regraded or retried as part of this change.

Complete prior sources and the external test are preserved under author_history/v1_calibrated with record/grade bindings. Earlier raw runs remain unchanged. The coordinator released the captured v1 backup identity through its already_recorded event at2026-10-31T22:27:05.521426+00:00 before any edit. Fresh calibration on these final exact source hashes remains a separate coordinator action.
