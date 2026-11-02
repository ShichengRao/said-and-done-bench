# Service v3: timed alternative delegated routes

This author-only certificate is outside the visible workspace. Version2's closed MiniMax attempt reconstructed its production availability, four-call obstruction and cost2 remedy; output-shape failures do not establish difficult canonical reasoning. Version3 preserves the entire prior source tree, nested version1 archive, external test and494 bound raw files from four closed version2 runs under `author_history/v2_calibrated/`. No prior inference or grade is changed.

The reusable API and admission/receipt semantics are unchanged. The explicit finite bound grows to six requests, three starts, two routes per request and at most six local options per request:46,656 possible complete assignments, with20,736 in the production instance. The current instance introduces alternative credential chains sharing tenant AND delegated service pools. Each distinct pool on a chain is charged once; repeated pool names on distinct credentials are not additional charges. The organization-wide pool and root credential retain the original identifier root. Its ample allowance is100.

## Ledger reconstruction

At cutoff9, `spent-C` is a permanently committed one-unit C charge accepted as attempt `accepted-C`. A later rejected retry under the same key offers a different chain using only the organization allowance. It does not rebind or refund the accepted call. The original commitment expires6 but remains spent; its repeated acknowledgment at9 is harmless.

Six outstanding accepted holds are A3 until11, A3 until12, B2 until12, C3 until12, D2 until11 and D1 until12. The C3 attempt has a timeout retry and an identical reserve acknowledgment; neither releases or doubles its hold. Another A1 reservation is already expired at cutoff9; an unacknowledged D attempt charges nothing. Exact authoritative budgets are A9,B5,C7,D6; the organization allowance100 is nonbinding. These observations yield:

| Start | A | B | C | D | Worker start capacity |
|---|---:|---:|---:|---:|---:|
|10|3|3|3|3|5|
|11|6|3|3|5|5|
|12|9|5|6|6|5|

Holds expire on half-open intervals, while newly admitted calls remain charged at every later start. Changing old bindings to the latest retry, refunding a rejected retry, or treating a timeout as release changes the actual admission answer; these are not merely report-field tests.

## Six indivisible calls

All durations are1. Requests0,1,3,4 may start10/11/12. Request2's credentials begin11; request5's credentials end12, so its last start is11. The request completion deadline is13. Each row has two approved chains (organization omitted below):

| Request | Units | First route pools | Second route pools |
|---|---:|---|---|
|0|2|A|B,D|
|1|2|A,C|B|
|2|2|A,C|B|
|3|2|A,D|B|
|4|3|A,D|B,C|
|5|3|A,C|B,D|

There is no legal full assignment. This is not an aggregate shortage: total worker capacity15 exceeds demand14, final A+B allowance equals14, and ignoring the earlier capacity profiles gives33 legal schedules. All four pool constraints are essential: omitting A,B,C,D separately gives61,372,2,5 schedules. Removing requests0..5 separately gives27,27,40,41,114,176 schedules. Thus the minimum obstruction contains all six calls. Every smaller request subset is feasible because feasibility is downward closed.

A compact algebraic reduction is also available. At the final slot, A+B must be exactly9+5, and the side-pool limits leave only one complete route pattern: requests3 and5 use B; every other request uses A. Its total C/D charges are4/6. That pattern has33 schedules if all final capacities were available initially, but none under the actual release times and worker slots. A separate time-by-time batch dynamic program finds25 legal first-stage states,30 legal second-stage states representing96 distinct prefixes, and no complete third-stage state. The main reference instead assigns requests in lexical order with resource backtracking; the grader independently groups ledger facts and enumerates Cartesian products. A peer independently reproduced all counts from the numeric fixture without importing either implementation.

## Genuine owner intervention

The offered approvals are C+1 cost2, A+1 cost3, B+1 cost4, D+1 cost1 and one additional worker unit at slot11 cost1. All32 subsets are evaluated. The minimum cost/count/lexical choice is `allowance-C`, cost2. It produces exactly two legal schedules; the least is:

* Slot10: request0 via A (2 units), request5 via B,D (3).
* Slot11: request1 and request2 via A,C (2 each).
* Slot12: request3 via B (2), request4 via A,D (3).

The other solution exchanges request0 and request1 between slots10 and11. Cumulative charges in the displayed witness are A2/B3/C0/D3, then A6/B3/C4/D3, then A9/B5/C4/D6. The approved C increase makes the middle C4 legal. Applying that approval to the actual data yields a ready report with no further owner request. A+1 yields5 schedules, B+1 yields33, and D+1 alone yields none. The independent certificate enumerates the exact offered combinations and verifies both the minimum and least assignment.

## Mechanisms, validation and scope

One-unit charging fabricates17,906 schedules. Using terminal allowance throughout fabricates33. Refunding the rejected retry, rebinding original evidence to the latest attempted chain, ignoring shared ancestor pools, and treating timeout as release all falsely admit this production batch. The original deadline/credential-boundary negative references remain checked on independent small instances. The start-window distinctions are legitimate authority constraints, but removing either or even both does not alone repair the shared-pool obstruction; no claim is made that each is independently necessary to this canonical failure.

Positive fixtures include every single owner approval, all32 proposal subsets, all proper request deletions, unordered records, identical replays, nonzero/time-shifted clocks, committed acknowledgments after expiry, timeout/rejected retry evidence, cutoff releases, and independent small generated ledgers. Every positive fixture retains declared references, parent acyclicity, valid historical chains, nonnegative reconstructed balances and the public request/route/start bounds. Invalid replay/reference/terminal cases remain explicitly labeled. Legitimate tests and helper files remain authorized; the trusted public suite runs separately.

No production calls are executed. The computed blocker follows from current authoritative evidence; hypothetical owner proposals do not alter it until applied as actual input.
