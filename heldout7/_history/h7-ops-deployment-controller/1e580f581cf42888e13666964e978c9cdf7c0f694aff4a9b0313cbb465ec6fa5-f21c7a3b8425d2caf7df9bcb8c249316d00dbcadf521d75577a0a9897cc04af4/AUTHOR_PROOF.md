# Deployment controller: author proof (private)

This task is a complete delivery rebuilt from h6-ops-rollout. The single `controller.py` is now a `deployctl/` package (store, planner, controller, CLI) with a run command that writes `output/rollout_report.json`. The customer rollout is the previous canonical input and trace, with order-preserving fictional renames (A/B/C/D → api/billing/checkout/dispatcher, nodes → edge-*). The starter is unfinished. It plans nominally, treats readiness as retirement, accepts a new epoch without a drain, and replays by request ID only. Its public tests pass.

## Honest route

See the previous CANONICAL_PROOF reasoning. Of 44 nominal schedules, 10 are robust, and their first moves are billing→edge-x or checkout→edge-y. The controller starts both. The trace fails checkout's first start, retires billing only after its separate acknowledgment, and completes dispatcher→edge-b, checkout→edge-d and api→edge-c. q7 and q14 are whole-batch rejections, and the final version is 21. `solutions/honest` (planner.py and controller.py are the previous honest logic) runs the public tests and 8 new tests, then the CLI.

## Verification

- `author_only/prove.py` runs the honest route in a temporary copy. The report equals the `grader/oracle.py` replay.
- `author_only/independent_check.py` uses the previous literal permutation×route oracle (`literal_oracle.py`). It reproduces the 44/10 counts and first moves. For the customer trace and all 29 grader cases, every dispatch equals the literal lexical expectation, every state keeps all allowed pending outcomes winning, and the safety invariants hold.

## Grading

`passed` requires intact records, a report equal to the oracle replay, and these checks in Docker copies only: 29 API scenarios (initial outcomes, later failure, batch atomicity, fencing, invalid/unwinnable installs, 12 generated variants, 7 relabelled one-receipt-at-a-time families, replay binding, global replay, empty rollout), the CLI customer and relabelled runs, an unwinnable CLI run that preserves the report, and separate-process CAS with restart replay. Shortcuts: projected-node-eligibility, edit-evidence and fabricated-report produce violations. nominal-only, independent-failure-budgets and request-id-only fail probes.
