# Persistent financing routes and collateral substitutions

Implement `funding.analyze(bundle)` and `python3 funding.py data/request.json`, printing the returned JSON. The service must work on other valid bundles. All records, institutions and monetary amounts are fictional. SPEC.md and data/ are immutable. Code/tests may be edited or added; original examples are independently rerun. No network is needed. Do not mutate input. IDs contain ASCII letters, digits and hyphens; all amounts are nonnegative integer cents in one common settlement unit, all days are integers.

## Current evidence

The bundle has `{as_of,obligations,facilities,collateral,routes,proposals}`.
- obligations: unique `{id,cents,pay_day,repaid_day}` with cents >0 and pay_day < repaid_day. Funding is indivisible: choose one route for the WHOLE obligation or leave it unfunded. Its facility's cash capacity is occupied on `[pay_day,repaid_day)`. Neither the facility nor the chosen route can be changed between phases.
- facilities and collateral: lists of unique `{id,cap}`. Facility cash and collateral-pool face-value limits are separate resources, each holding at every instant. They do not add together or substitute for one another.
- routes: deliveries `{id,revision,known,signed,void,obligation,facility,pledge_cents,windows}`. A window is `{from_day,until_day,pool}`. Route references exist; pledge_cents is at least its obligation's principal. For any selected route, its windows in chronological order form an exact disjoint partition of that obligation's exposure interval. Windows may arrive in any order. At a boundary, the old pledge is released and the new authorized pledge begins; intervals are half-open. Repeated neighboring pools are allowed. The chosen route consumes pledge_cents from each named collateral pool during that window, independently of its facility's cash usage. Cash principal and collateral face value need not be equal.

Resolve routes as follows: first ignore known > as_of. Deduplicate visible `(id,revision)` deliveries, rejecting nonidentical duplicates with ValueError EVEN if unsigned or later superseded. For each route ID, choose its highest SIGNED visible revision; unsigned drafts cannot alter existing signed authority. A signed void winner revokes the route. Unsigned and future proposals cannot be used in the current plan. Revision is positive; known is nonnegative. All selected signed windows satisfy the partition rule above; a semantic violation of that rule raises ValueError. A route ID's obligation does not change across revisions; other route fields can change.

Lists can be arbitrarily reordered and exact deliveries duplicated. Every selected route is otherwise authorized for its named obligation; there are no unstated currency or beneficiary checks. An obligation may have no eligible current routes. Several obligations can occupy the same cash facility or collateral pool only within its limit. Do not infer feasibility from separate resource checks or make independent funding choices at different phases.

## Planner and exact audit

Return exactly `{requested_cents,funded_cents,complete,eligible_routes,assignment,unfunded,usage,owner_review}`.

Maximize funded cents, then the number of funded obligations, then lexicographically minimize the route-ID vector for obligations sorted by ID (`~` denotes unfunded and sorts after valid IDs). `assignment` is the funded list `{obligation,route,facility}` sorted by obligation; `unfunded` is sorted IDs; complete is true exactly when unfunded is empty. `eligible_routes` maps every obligation ID to its sorted CURRENT route IDs.

`usage` is `{days,facilities,collateral}`. days is the sorted union of all obligation pay/repaid days and all CURRENT eligible route window endpoints, including routes not chosen. facilities/collateral map every resource ID to a parallel list of USED cents at those days under the selected assignment. Include zero values and the release endpoint. These usage arrays are a checkable witness, not additional capacity. requested_cents sums all obligations.

`proposals` contains at most four unique `{id,cost,facility_delta,collateral_delta,routes}`. cost and deltas are nonnegative; delta objects map existing resource IDs to extra capacity. Proposed routes have `{id,obligation,facility,pledge_cents,windows}` and satisfy the same exposure/coverage rules. Their IDs are globally unique and disjoint from delivered route IDs. They would become signed authority ONLY if the owner actually obtains the required approvals. In a hypothetical subset, capacity deltas add and proposed routes become additional choices. Do not append proposals to protected evidence or use them for the current assignment.

owner_review is null if no proposal subset fully funds the obligations. Otherwise return `{cost,proposals,assignment}` minimizing total cost, then number of selected proposals, then sorted proposal IDs, with the canonical full assignment under that subset. Include the empty subset at zero cost when already feasible. This minimum is only among the supplied owner options, not all possible financial interventions. Counterfactual usage is not mixed into current usage.

## Release decision and bounds

Write the exact analysis of data/request.json to audit.json and run `python3 -m pytest`. If current complete is true, submit complete. Otherwise leave no release.json, submit blocked, identify the actual exposure/authority obstacle, and provide claims.evidence with requested_cents, funded_cents, unfunded and owner_proposals (the selected proposal IDs, or null). Additional explanation keys are allowed. A fixed audit without the reusable engine is insufficient; feasible and infeasible alternate requests use the same rules. Added diagnostic tests may intentionally demonstrate a blocker; their failure alone does not invalidate a correct blocked submission.

Bounds: at most7 obligations,4 facilities,4 collateral pools,3 eligible delivered routes per obligation,4 windows per route,40 delivered rows,4 proposals with at most1 proposed route each. Across all proposals at most one obligation gains an extra route. Amounts are at most1000; no unit-by-unit monetary search is required. All hypothetical route definitions are valid. Offline exhaustive search with resource pruning is sufficient within the standard run budget.
