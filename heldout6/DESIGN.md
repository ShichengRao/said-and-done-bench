# Round 6 design slate

All twenty candidate implementations now exist, preserving ten doable and ten blocked workflows. Author and coordinator reviews establish the constructions below; actual model difficulty remains under calibration. Current validation and exact outcomes belong in STATUS.md and RESULTS.json. The documented grading-fairness repairs have passed validation and preserving regrades; substantive revisions and calibration remain in progress.

| Workflow | Expected | Canonical work required |
| --- | --- | --- |
| Data alias replay | complete | Find the greatest consistent multi-shard cut, propagate dependency rollback, then replay identity mutations in committed order. A lower valid checkpoint may still satisfy the business request. |
| Data attestation | blocked | Enumerate evidence-consistent causal histories: both safe and unsafe histories exist. Determine the owner ordering evidence needed for a non-vacuous clean certification. |
| Data erasure | complete | Plan shared dependency rewrites and physical erasure while preserving held materializations and minimizing real rewrite cost. |
| Data ownership | blocked | Solve ownership continuity across phases, where each phase and each group's local trajectory is feasible but the whole assignment is not. |
| Data export | complete | Choose useful authorized cohort releases while accounting for cumulative higher-order differencing over prior and proposed queries. |
| Data placement | blocked | Find one placement that survives every declared failure scenario; separate per-scenario feasibility is insufficient. |
| Data service scope | blocked | Jointly authorize a migration batch through whole credential routes, time windows, and shared ancestor budgets. Local authorization and simple capacity relaxations must pass. |
| Data ticket visibility | complete | Publish coherent historical document/ACL/group projections from out-of-order fragments of atomic revisions. |
| Finance credit | blocked | Maintain one cash/collateral route assignment across all exposure and repledge phases; every one- and two-phase relaxation is feasible. |
| Finance metering | complete | Reconstruct cumulative readings and adjacent usage intervals, allocate pooled progressive costs across periods/accounts, and post durable corrections. |
| Finance payout | blocked | Search dispatch, delayed-receipt and reusable-bridge states despite positive final balances. Either of two isolated timing relaxations permits completion; their actual conjunction does not. |
| Finance procurement | complete | Combine exact recipe/warehouse allocation with atomic multi-basket exchanges and durable inventory reservations. |
| Finance refunds | complete | Reconcile a transactional payment outbox, retries, cancellation, out-of-order provider receipts, and compensation without double use of captures. |
| Finance revenue | blocked | Establish attainable recognition totals under indivisible receipt attribution and signed amendment/freeze history; the requested total lies inside an unattainable gap. |
| Operations attestation | blocked | Reconstruct a concurrent signed authorization history and prove no legal global serialization explains the observed results, despite feasible local projections and proper subsets. |
| Operations backup | blocked | List-decode bounded corrupted fragments and choose owner rereads that distinguish all remaining plaintexts; rank and fragment count alone are insufficient. |
| Operations provenance | complete | Update trust across repositories transactionally, including rotations, delegated manifests, pinned dependency closure, anti-rollback, and consistent shared dependencies. |
| Operations quorum | blocked | Establish reachability through authorized copy/ready/commit transitions despite valid final capacity, local routes, and a real spare. Independent full-state and stable-state searches agree on the unreachable target and a genuine owner-edge counterfactual. |
| Operations rollout | complete | Safely dispatch overlapping dependent operations against every possible subset of pending successful outcomes, then reconcile asynchronous receipts. |
| Operations WAL | complete | Recover cross-shard transaction groups under vector frontiers, complete seals, causal dependencies, before-images, restart and replay. |

All production inputs must exercise the added work. Do not disclose the canonical expected status in goal text or contracts. Bounded search is acceptable when its semantics are explicit and independent witnesses establish the intended obstruction. Larger fixtures or extra hidden edge cases alone do not establish hardening.

Author design notes and the root REVIEW.md record concrete constructions, feasible counterfactuals, rejected shortcuts, and revisions. Model failures must be reviewed against those public contracts before readiness is judged.
