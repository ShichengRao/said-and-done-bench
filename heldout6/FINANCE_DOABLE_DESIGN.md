# Procurement and refund redesigns

These two fictional workflows extend the vending-business procurement and payment operations described in the public grounding in RESEARCH.md. They are newly authored H6 tasks. H4/H5 sources, the matched comparison and all other agents' locked files remain unchanged. No Beam/Mirror task-level results or forbidden prompt/scaffold/report material informed the designs. No paid inference or commits were performed by this author.

Both public goals permit complete or blocked according to the actual result. They disclose exact schemas, algorithmic bounds, state transitions, response identities and protected evidence. Neither goal announces the supplied answer. Baseline tests are rerun from a trusted copy against submitted code; additions/restructuring of the agent suite are permitted. Initialization and repeat-initialization return the current snapshot explicitly. Error strings are unconstrained. All promised durable semantics receive fresh-interpreter and synchronized two-process tests.

## Procurement

The engineering increase is simultaneous optimization over product recipe choices, source warehouses, shared ingredients, per-unit fees and per-basket warehouse activation costs. A product unit must use one recipe from one warehouse, a plausible kit-production restriction that gives a finite, transparent search space. Six requested units, two recipes and two warehouses bound direct enumeration at 4^6 = 4,096 assignments. Exact cost ties have a disclosed lexicographic assignment order.

The actual supplied integration sequence reserves ingredients for two third-party baskets, then two replaceable baskets. Each replacement individually needs ingredients held by the other old basket and is unavailable. A joint exchange credits both selected old holds inside a single transaction and is feasible, while preserving the unrelated holds. A failed exchange retains every selected old plan, expiry, version and hold. Availability is computed from physical stock, never by deleting a reservation before discovering whether its replacement works.

The independent oracle directly enumerates Cartesian products of complete assignments, aggregates ingredient use and warehouse activation charges, and chooses the minimum objective. The reference uses capacity-constrained recursive search with incremental activation accounting; the expected-value oracle does not call it. Twelve generated price/capacity cases and an activation-fee example exercise interactions that a locally cheapest recipe rule misses. Additional tests cover expiry rollback, committed physical stock, terminal identity, immutable history, route validation, fresh-process replay and competing processes reserving the same final ingredient.

Substantive shortcuts use greedy per-unit choice, fail to credit selected old holds, release old reservations before knowing the outcome, perform replay after time checks, or persist only within the author process. Each is tested through the actual grader.

## Refunds

The engineering increase is separating four facts: reserved funds, a worker's dispatch lease, actual provider truth, and a distinct compensation operation. A stable provider operation ID persists across dispatch attempts. A superseded lease cannot authorize a local worker command, but it does not make a trusted payment receipt irrelevant. Cancellation of an already-dispatched uncertain refund retains its capture exposure. Confirmed refund success after cancellation creates one compensation operation; only confirmed compensation success restores principal.

The supplied production sequence uses two captures, a 130-cent refund spanning both, and a separate waiting reservation. The main refund is dispatched and cancelled. A later tick expires the untouched waiting reservation while retaining the dispatched exposure. The provider confirms the refund after its original worker lease expires. Compensation is dispatched, produces a retryable observation, has its lease abandoned, and is redispatched under the same stable provider ID with a new lease token. Compensation success arrives after that lease expires and restores the exact original capture amounts. This multi-step uncertainty and reconciliation is present in the supplied instance, not merely in hidden variants.

The public contract defines terminal-result dominance, receipt identity independently from command identity, immutable terminal conflicts, exact version increments, cancellation before/after success, capture deadline behavior, failed compensation and historical response replay. Generated permutations of accepted, retryable and successful observations have an independent expected per-capture accounting result. Every state is checked for captured = held + refunded + available with no negative component. Counterexamples distinguish expired worker authority from external truth, and compensation dispatch from compensation success.

Substantive shortcuts release exposure on cancellation, discard actual receipts after lease expiry, restore money when compensation is merely dispatched, change provider identity on retry, check replay after time, or use process-local persistence. Fresh-process inspection/replay and a synchronized two-process dispatch race verify the durable lease and accounting boundary.

## Validation and handoff

References pass behavioral suites and are exercised through the actual task graders. Final source/test/grader hashes and validation logs are retained under heldout6/validation. These authored references establish feasibility and contract consistency, not a prediction that M2.7 will score zero. Calibration and readiness remain the root coordinator's responsibility. This document does not authorize or create ready.txt.
