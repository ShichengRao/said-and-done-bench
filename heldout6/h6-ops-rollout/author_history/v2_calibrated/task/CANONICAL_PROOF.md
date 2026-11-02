# Rollout v2: completion-preserving asynchronous dispatch

This is a substantive planning revision, not a grader-only repair. The closed v1 M2 run solved the supplied four-action rollout. V1 also left the element type of `done` unspecified, while its grader expected action-ID strings; that wording ambiguity must not be described as failed rollout reasoning. V2 specifies that type and adds completion-preserving dispatch, a new six-action production instance, and a supplied asynchronous request trace. The prior task, grader, external test and all closed run bindings are preserved under `author_history/v1_calibrated/`; the original raw runs are untouched. No model result for v2 is claimed here.

## Instance and obstruction

The API service has size two, requires two ready replicas and requires both west and east zones. Each rack has capacity four and three node slots, each of capacity two. Initially each rack contains one old replica. The final target contains the replacement and an expansion replica in each rack. Let A/B/C/D/E/F denote the six action IDs in their lexical order:

| Action | Effect | Explicit prerequisite |
| --- | --- | --- |
| A | Expand west | None |
| B | Copy east | None |
| C | Copy west | None |
| D | Expand east | None |
| E | Retire old east | None |
| F | Retire old west | C acknowledged |

West must execute C, F, A. Taking A first is safe immediately, but fills the spare capacity. C cannot then start, and F cannot free capacity until C succeeds. Thus A has zero completions. East can execute B, E, D or D, E, B: its old replica cannot retire before another east replica exists, and its two new replicas cannot both start before retirement. Each east order has 20 interleavings with C,F,A, giving exactly **40** safe complete sequential orders. Safe initial first actions have completion counts **A=0, B=10, C=20, D=10**. The full-success projection after B+C has six suffix orders; after B+C+F it has three.

The current dispatch rule rejects A using completion lookahead and selects B,C. Removing lookahead selects A,B and creates the west dead end. Checking only the full-success outcome selects B,C,E: that combined success state is safe, but E succeeding alone removes the last east-zone replica. After C succeeds while B remains outstanding, D would be safe if viewed in isolation but cannot join B: old east+B+D consumes six against capacity four. Correct dispatch selects only F; ignoring previously pending commands instead selects D,F.

These are three genuine canonical distinctions: completion feasibility, every-success-subset safety, and inclusion of outstanding work. The explicit reservation inequality is redundant with the all-starts/no-stops subset of exhaustive safety. It is not presented as an independent ablation. The three-command total window is covered by a separate valid capacity-six fixture; the canonical instance does not need artificial padding to make that bound decisive.

## Supplied request trace

The workspace contains requests, not expected answers. An install makes version one. Subsequent accepted operations are:

| Operation | Result needed by the contract | New current version |
| --- | --- | --- |
| Dispatch copies | B1,C1 pending; observed unchanged | 2 |
| Acknowledge C1 | C done; B1 still pending | 3 |
| Dispatch | F1 joins B1; D remains excluded | 4 |
| Fail B1 | Failure permits retry, not descendants | 5 |
| Dispatch | B2 joins still-pending F1 | 6 |
| Batch F1 success then B1 success | Reject entire batch: B1 was settled failed | stays 6 |
| Batch F1 success then B2 success | Both accepted | 7 |
| Dispatch | A1,E1 pending | 8 |
| E1 success twice in one batch | Applied then replayed; one state change | 9 |
| Dispatch | D1 joins still-pending A1 | 10 |
| Acknowledge D1 before A1 | D done, A still pending | 11 |
| Dispatch | No new command | 12 |
| Replay original dispatch request | Original version-two response; current state unchanged | stays 12 |
| Acknowledge A1 | Exact target, all six IDs done, no pending work | 13 |

Pending actions count as done only inside the hypothetical completion search. Actual eligibility still requires acknowledged prerequisites, and neither dispatch nor hypothetical search changes observed state. The failed B1 token cannot later become a success for B2. The rejecting mixed receipt batch proves that an earlier valid receipt must not partially commit before a later conflict.

## Independent validation and finite bounds

The honest controller searches completed-action subsets. A valid completed subset determines its inventory uniquely: per node and service/image identity, initial occupancy plus starts minus stops determines the final occupancy. With at most eight actions there are at most 256 completed subsets. The independent oracle enumerates literal permutations (at most 8!=40,320) and all combinations of up to three pending successes (at most eight), rather than calling or copying that search. Both agree on the canonical counts and full request trace. A separate reviewer reproduced the counts and dispatch distinctions using set-valued placements and literal permutations without importing the author engine.

The actual grader reads the new production data and compares every request with the independent oracle, including rejection rollback, duplicate receipts and old request replay. Twelve generated positive rollouts vary rack capacities, the true prerequisite, maximum window and action-ID order while retaining valid references and bounds; each includes a failure/retry and partial receipts. Existing four-action tests remain general regressions for durability, process concurrency, CAS, epochs and invalid plans. Negative reference implementations separately omit completion lookahead, omit prior pending work, or use only the full-success outcome, and each differs on this supplied instance.
