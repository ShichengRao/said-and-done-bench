# Credit v3: financing changes what may be observed

The public input is fictional. The canonical wall comes from a nonanticipating financing policy with action-dependent authenticated observations, persistent cash and collateral exposure, a frozen accepted commitment, and a later collateral substitution. No missing file or unexplained permission is the obstruction.

## Exact v2 preservation

Before any source edit, the entire previous tree, including its existing nested v1 author history, was copied to `author_history/v2_calibrated/`. Its manifest binds 65 previous source/history files, the previous external test, and file hashes of all three closed v2 runs. The v2 task/grader identities are `ed738c7987eca55639600f0ab38db2e95347557f45b91247c5d40da6e680df9a` / `3ab92aaba17091bfa1fec49266a7a10d153de29e4396e58f60353712a0855e1e`. The archive manifest SHA is `2f19b4eef2b1be83cd31cdd4a480dc06ab085c7bafd250f352ac1fda14cb4d88`. No earlier run or review is rewritten.

V2's model implemented the static-history policy search correctly and lost on authority serialization and claims. V3 changes the policy's information dynamics. An observation tree cannot be constructed from scenarios alone: the chosen funding route determines the later report entitlement. This is a substantive mechanism change, not a claim that a larger minimal core alone creates hard engineering.

## Literal numerical certificate

Divide cents by 100. Let x, y, z be one for the P route of O1, O2, O3 respectively and zero for Q. At stage 3, the exact accepted F revision still consumes cash A=1 and substitutes its pledge R→P. The newer F offer B/Q does not replace it. Thus:

- A = 2 + x − y; B = 1 − x + y; C = 1.
- P = 1 + x + y + z; Q = 3 − x − y − z.
- The common limits require 1 ≤ x+y+z ≤ 2.
- X-cash further requires x≤y; X-pledge requires x+y+z=1.
- Y-cash further requires y≤x; Y-pledge requires x+y+z=2.

The four independent full-information scenario plan counts, in sorted case order X-cash/X-pledge/Y-cash/Y-pledge, are 4/3/4/3. These do not constitute an executable common policy.

O1 is funded at stage 1 before the family is known. Stage 2 reveals X versus Y; full case identity arrives only at stage 3. O1-P earns inspect-Y at stage 2; O1-Q earns inspect-X at stage 2. Each inspection distinguishes its two named-family cases and returns the same `outside` label for the other family. An unchosen route grants no report.

If x=1, the X cases are still indistinguishable at O2 funding. X-cash requires y=1, but X-pledge requires y=0. If x=0, the Y cases are still indistinguishable: Y-cash requires y=0, but Y-pledge requires y=1. No first choice works. All four cases form the sole inclusion-minimal core. Every proper triple has six feasible policies; all pairs and singletons are also feasible.

## Actual prospective remedy and causal checks

P-enable-X, cost 2, adds inspect-X only to the future O1-P route. Choosing it funds x=1 and earns both reports at stage 2. The X cases now take distinct O2 routes, while Y decisions may also branch. This gives six distinct reachable policy tables. Q-enable-Y costs 3 and symmetrically gives six; granting both gives twelve. An all-at-3 disclosure costs 1 but arrives too late. Extra-P costs 3 and gives 24 policies. Therefore P-enable-X is the minimum supplied owner intervention. No report is treated as already delivered in the base case.

The root choice in the least owner policy is O1-P. At stage 2 its X-cash case chooses O2-P and X-pledge chooses O2-Q; the least Y-case actions both choose O2-P. The least leaf action is O3-Q in each world. There are nine reachable decision nodes: one root, four second-stage nodes, four third-stage nodes. No other histories receive arbitrary actions.

Useful independent ablations:

| Assumption changed | Base policies |
| --- | ---: |
| Correct original input | 0 |
| All offered inspections delivered unconditionally | 12 |
| All future case IDs known at every decision | 144 |
| Accepted commitment incorrectly re-resolved to the newer offer | 3 |
| Frozen commitment omitted | 72 |
| Accepted R→P substitution removed | 24 |
| Cash limits ignored | 24 |

Ignoring earned inspections or delivering them one stage late preserves a zero base count but wrongly makes the cheapest owner remedy the cost-3 capacity option. Thus correctness includes the evidence and genuine feasible counterfactual, not just a blocked label. A late-inspection variant where every receipt arrives at stage 3 remains infeasible even after P-enable-X. A perfect-recall alternate delivers both inspections through the exact accepted F at stage 1 and has 144 policies despite later common messages.

## Independent engineering checks and bounds

The reference recursively partitions possible worlds by the full observation history under the already chosen financing prefix, chooses one action per information set, and combines feasible continuation counts. The separate oracle independently reconstructs signed authority, frozen payloads, time-expanded resource use, and inspection receipts. It enumerates feasible complete per-scenario route profiles, rejects profiles with different actions at an identical history, and deduplicates complete reachable tables. It does not import the reference engine. Literal arithmetic above is additionally asserted without either implementation.

The canonical case has eight full route vectors per scenario, so the unfiltered profile product is 8^4=4096. The prospective-route alternate has 12^4=20736. Every valid authored fixture, every owner-proposal subset and every nonempty scenario subset is explicitly checked against the public 65,536 bound; no arbitrary cutoff substitutes for proof. Partial inspection labels, grant deduplication, late receipts, exact accepted entitlements, reachable-domain counting, perfect recall, simultaneous funding, signed revision conflicts, input order, optional route interventions and empty new requests are covered. Public tests include both a feasible earned-inspection example and its blocked no-entitlement counterpart.

The actual grader tests the honest implementation, seven substantive shortcuts, fixed-artifact submissions, incorrect complete submissions, protected-evidence violations, truthful extra explanation, ordinary conftest helpers and legitimate test restructuring. No model inference is performed as part of author validation. This document does not predict a model or Beam score, and it does not declare readiness.
