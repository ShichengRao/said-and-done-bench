# Owner-merge v2 canonical coverage proof

This is author-only evidence, outside the visible workspace. The public contract retains the same history and planning semantics and does not reveal the supplied instance's conclusion.

The previous calibrated v1 had no active current handoffs. The parent reported that M2.7 correctly diagnosed that production instance and wrote its canonical artifact, while failing a generated variant. That failure does not establish failed canonical diagnosis. The v2 revision makes phase-specific authority necessary on the production instance and on concrete approved remedies. It uses no Beam task-level evidence. V1's complete task/grader/solutions and external test are retained in author_history/v1_calibrated with hashes; the coordinator's original source archive and all raw attempts remain unchanged.

## Reconstruction and finite bounds

The 39-row ledger freezes the same seven records into accounts, contacts, tickets and warehouse. The three variable groups have phase loads (2,2,1), (2,1,2), and (1,2,2). Alpha and beta each have capacity (3,3,3). Warehouse has its independent gamma-only load/capacity (1,1,1).

Zero-load members still constrain group authority: accounts-history0 permits only beta at phase2, and tickets-history0 permits only beta at phase0. Their other effective revisions permit alpha and beta. Two approved current grants transfer accounts alpha→beta only at boundary1 and tickets beta→alpha only at boundary0. A later phase does not inherit permission for a different boundary. The tickets late beta→alpha grant remains revoked at cutoff10, with its old approval available at cutoff7 and later reapproval available at cutoff12. The unapproved alpha capacity revision remains excluded.

Using A=alpha and B=beta, the current legal paths are:

| Group | Legal paths |
| --- | --- |
| accounts | AAB, BBB |
| contacts | AAA, BBB |
| tickets | BAA, BBB |
| warehouse | gamma/gamma/gamma |

There are exactly eight full legal path products, all infeasible. Every singleton and pair within the three-group obstruction has exactly two feasible assignments; retaining warehouse does not change them. The independently feasible phase assignment counts are 2, 4, 2. These statements concern proper subsets of the minimal three-group obstruction, not every proper subset of the four-group production plan.

## Joint obstruction

Contacts has a constant owner C. Phase0's two-unit accounts and contacts loads force A0≠C. Phase2's two-unit contacts and tickets loads force T2≠C, hence A0=T2. Accounts can change only at boundary1, so A1=A0; tickets can change only at boundary0, so T1=T2. Thus A1=T1. Their combined phase1 load is four, exceeding either owner's capacity of three.

A fractional assignment using half of each group's two legal paths is feasible. Alpha usage is (2,2.5,2), beta usage (3,2.5,3), and gamma usage (1,1,1). The supplied instance therefore needs compatible whole-group paths; independent phase plans, local paths, aggregate capacity, proper-core-subset checks and this fractional relaxation do not settle it. Removing both current grants destroys the fractional witness and causes a smaller obstruction, so the current grants are substantive authority rather than decorative ledger rows.

## Distinguishing grant timing and approved remedies

Shifting either active grant to the other boundary, or broadening just that grant to both boundaries, produces exactly one complete assignment under otherwise identical rules. A boundary-blind shortcut therefore incorrectly calls the production instance feasible.

The cheapest supplied owner intervention is tickets-late-handoff, cost2. Its unique joint assignment is accounts AAB, contacts BBB, tickets BBA, warehouse gamma/gamma/gamma. It uses the existing accounts boundary1 grant. Removing that current grant makes the reapproved tickets-late remedy insufficient.

The cost3 accounts-early-handoff instead gives accounts ABB, contacts BBB, tickets BAA and requires the current tickets boundary0 grant. The alternative cost4 phase-one-alpha-lease raises only alpha's phase1 capacity to four; its unique witness is accounts AAB, contacts BBB, tickets BAA. Removing either current grant defeats that successful counterfactual. Both are prospective approvals, never current authority.

Earlier cutoff7 and later cutoff12 both restore the authorized tickets late handoff and are independently feasible. All owner proposals combined yield at most 18 legal path products, within the public product bound of4096; each group remains below the eight-path limit.

## Verification

The honest engine reconstructs merge closures using union-find and selects eligible revisions before capacity-pruned path search. The independent oracle uses graph components, sorted revision reduction and whole-matrix filtering. External tests separately count the eight canonical products and every proper core subset, verify the phase counts and exact doubled fractional usage, and check that the cost4 remedy needs both grants. Generated and metamorphic fixtures have explicit reference/bound checks; subset fixtures remove associated record/merge/handoff references and obsolete group proposals together. The actual grader checks an added boundary-blind shortcut alongside future-approval, superseded-grant and ignore-continuity shortcuts.
