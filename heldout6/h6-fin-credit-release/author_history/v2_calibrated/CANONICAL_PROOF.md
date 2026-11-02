# Credit v2 adaptive-policy certificate

Author-only evidence, outside the model-facing workspace. V1 was fully passed by M2.7 according to parent review; its success remains part of the benchmark evidence. The exact v1 task, grader, solutions and external test are preserved in author_history/v1_calibrated with a byte manifest; existing scheduler archives and model records/logs/snapshots/grades remain unchanged. This revision addresses a substantive gap in the supplied planning problem, using no Beam task-level evidence.

## Prospective decisions and frozen past authority

The ledger cutoff20 is independent of the planning stages. Frozen F was accepted before the stage0 planning boundary using F-route/revision1, bank A and pool P. Its100-cent exposure continues through stage4. A later current quote for F-route uses bank B/pool R, but cannot rewrite that accepted contract. O1, O2 and O3 are all unfunded future obligations, paying at stages1,2,3 and repaying at4. Earlier-disclosure interventions obtain authenticated records before those future decisions; they do not change past knowledge.

Use100 cents as one unit. Bank capacities are A3/B2. Every current route choice fits local capacities at stages1 and2. O1-P uses A/P; O1-Q uses B/Q. O2-P uses B/P, O2-Q uses A/Q, and current O2-H uses B/R in[2,3) then B/P in[3,4). The selected signed H revision2 supersedes revision1's neutral R pledge; an unsigned draft and a future signed version also retain R but are not current authority. O3 has the sole A/Q route. Principal and pledges remain committed through stage4.

At stage1, a signed preliminary message distinguishes group X from group Y. Stage2's common pending message does not erase that distinction. The full case is authenticated only at stage3. Final collateral limits are:

| Scenario | P | Q | R |
| --- | ---: | ---: | ---: |
| X-low | 1 | 3 | 1 |
| X-balanced | 2 | 2 | 1 |
| Y-high | 3 | 1 | 1 |
| Y-balanced | 2 | 2 | 1 |

All earlier pool limits are P4/Q4/R1. Scenarios sharing an observed history have identical currently observable capacities. Their future differences cannot be used early by a policy.

## Full-information feasibility and information deadlines

Frozen F plus O3 require A2/P1/Q1. O1-P combined with O2-Q would add another A2, exceeding A3. This cash constraint excludes that pair even when collateral alone fits. The complete ex-post new-route vectors are:

| Scenario | O1 | O2 | O3 | Count |
| --- | --- | --- | --- | ---: |
| X-low | Q | Q | Q | 1 |
| X-balanced | Q | P or H | Q | 2 |
| Y-high | P | P or H | Q | 2 |
| Y-balanced | Q | P or H | Q | 2 |

Every scenario is therefore feasible, and every stage1/2 local funding choice fits immediate capacity. Nonetheless, no current nonanticipating policy exists. X can choose O1-Q before its leaf is known, but must distinguish its leaf before O2 at stage2. Y must distinguish its leaf before O1 at stage1. The two inclusion-minimal infeasible uncertainty cores are [X-balanced,X-low] and [Y-balanced,Y-high]. Cross-group pairs can use their authenticated preliminary distinction.

The unique minimum-cost owner option set is X-authenticated-leaf-at-2 (cost1) plus Y-authenticated-leaf-at-1 (cost2). It has eight valid deterministic policy tables: 1×2×2×2. Revealing both leaves only at stage2 still fails, because Y's earlier O1 commitment cannot be repaired. The least policy uses O2-H where P/H are interchangeable, since route IDs break ties lexicographically. Policy tables include only observed histories present in these scenarios, with no arbitrary actions on absent branches.

## Substantive ablations and genuine counterparts

* Granting advance knowledge of the scenario falsely yields8 base policies. Independent ex-post witnesses are not an executable policy under the actual disclosure schedule.
* Taking superseded H's neutral R pledge yields one false current adaptive policy: O1-Q in X, O1-P in Y, and H for O2. The current approved substitution to P is therefore essential to the obstruction.
* Re-resolving accepted F to the later B/R catalog offer yields one false current policy: O1-P in both groups, O2-Q in X and O2-P in Y. Dropping F's exposure altogether yields six false policies. Exact accepted revision and continuing resource use both matter.
* Ignoring cash leaves the base infeasible, but changes the minimum owner remedy to cost2, revealing both leaves at stage2. Cash and collateral jointly determine different information deadlines; this is not a generic static robust-placement conflict.

Approved neutral-R route, future P-capacity increment and earlier-disclosure counterparts are valid under the same rules. Once an option is materialized as an alternate input, it is removed from the still-prospective proposal list, preserving disjoint route identities. A legitimate alternate accepted F revision2 is feasible and requires remembering X/Y at stage2 despite the common current pending message. It tests perfect recall without asserting that the real accepted revision changed.

## Independent verification and finite state

The reference reconstructs current offers and separately dereferences accepted revisions, then recursively counts policies over successively refined information sets while retaining past route commitments. The independent oracle enumerates complete deterministic policy tables and checks every scenario with literal resource sums; it does not share the policy search. A separate test derives the canonical allowed route pairs directly from A/P/Q inequalities and verifies the five shortcut effects.

The canonical base has36 possible policy tables before resource rejection; all owner options together have4096. The public product bound remains4096 for each proposal subset, including every proposed route. Current-route allowance is four, so a valid owner-approved new route can become a current offer without leaving the published input class. The fixture guard caught this boundary during authoring, before model inference. It also checks all proposal subsets, source references, immutable accepted anchors, observation/capacity consistency, and the disjointness of newly approved route IDs.

Generated and metamorphic checks include simultaneous funding batches, repayment/substitution endpoints, nonzero exposure, exact duplicate histories, future versus visible conflicts, current-offer revocation without undoing an accepted contract, restricted uncertainty sets with filtered disclosure references, and an empty new request that still accounts for frozen exposure. Actual-grader tests cover the honest engine, all five substantive shortcuts, standalone alternate-input CLI behavior, protected evidence, false completion, and legitimate conftest/test reorganization.
