# Attestation v2 canonical coverage proof

This author-only note is outside the agent workspace. The public contract states the reusable rules and status scope without revealing the supplied instance's result.

The parent reviewed the closed M2.7 v1 attempt: it passed the hidden and baseline checks and produced the exact canonical artifact; its full grade failed solely because it submitted complete while ready was false. That status error is not evidence of hard canonical reasoning. V2 adds observed state-dependent constraints and immutable delegated capability lineage on the production instance. No Beam task-level evidence was used. Exact v1 task/grader/solutions and external test are preserved under heldout6/h6-data-attestation-conflict/author_history/v1_calibrated, together with the existing coordinator archive and unchanged original raw evidence.

## Ten recorded events

There are three sealed chains of lengths3,4,3. Initially the document is owned by alpha/version0. root0 delegates from alpha to broker; leaf0 delegates from broker to auditors and binds the exact parent root0. Both slots begin at generation0.

| Chain | Recorded facts |
| --- | --- |
| A | a1: failed leaf-slot revoke-CAS expecting generation0; a2: successful owner CAS0 alpha→beta; a3: successful owner CAS1 beta→alpha |
| B | b1: document copy capturing owner/version and leaf capability/ancestry; b2: failed owner CAS expecting version1; b3: descendant of b1 retaining its provenance; b4: acknowledged descendant delivery |
| C | c1: successful root revoke; c2: successful root reissue as a new incarnation; c3: successful leaf renewal bound to c2 |

A signed cross-system edge puts c2 before b4. A revoke's predicate checks only the slot generation; failed a1 cannot be explained by missing parent authority. Copy and receipt facts are never filtered by their authorization status.

## Independent position proof

Sealed-chain shuffles plus c2<b4 yield3600 structural orders. Failed a1 requires c3<a1, because c3 is the only successful leaf-generation change. Failed b2 requires b2<a2 OR a3<b2, excluding the document-version1 interval. Exactly187 structural orders satisfy those two conditions; all remaining successful operation preconditions hold in them.

A safe order must capture the renewed leaf, c3<b1, and capture alpha ownership, b1<a2 OR a3<b1. Every old leaf capture is invalid at b4: root0 was revoked before c2, and c2<b4. These independent positional predicates yield25 safe and162 unsafe histories. Their mixture establishes missing chronology, not a proven historical unauthorized delivery.

The least unsafe order is b1,b2,b3,c1,c2,b4,c3,a1,a2,a3. It captures owner alpha/version0 and leaf0 with ancestry[root0,leaf0]. At receipt root0 is no longer current, although the root slot contains c2. It is therefore stale ancestry, not missing audience scope. The exact original parent cannot be replaced by c2.

## Minimum nonvacuous owner evidence

The minimum qualifying proposal subset has cost3:

* owner-diagnostic-before-return, cost1: b2<a3. Combined with the failed owner CAS, this forces b2<a2, and hence b1<a2.
* capability-diagnostic-before-copy, cost2: a1<b1. Combined with the failed revoke-CAS, this forces c3<a1<b1.

Together they preserve six feasible histories, all with fresh delegated capability and original alpha provenance. The first is c1,c2,c3,a1,b1,b2,a2,a3,b3,b4. Neither proposal by itself certifies all histories. A direct child-renewal fence plus the owner diagnostic costs4; a direct copy-after-owner-return fence costs5 and leaves one feasible clean history.

The apparently plausible cost2 pair b2<a3 and a2<b1 has322 structural orders but zero outcome-consistent orders. It cannot certify safety. A cycle is not needed to expose the nonvacuity requirement: the recorded failure itself contradicts this proposed ordering.

## Mechanism ablations

Each new rule changes the supplied-instance evidence or minimum remedy. These counts were independently reproduced using only stream shuffles and positional predicates, without importing either task engine.

| Interpretation | Consistent / safe / unsafe | Minimum purported remedy |
| --- | --- | --- |
| Correct | 187 /25 /162 | Cost3 diagnostic pair;6 histories |
| Ignore failed capability observation | 2634 /65 /2569 | Cost4 direct-child fence plus owner diagnostic;40 histories |
| Ignore failed owner observation | 205 /31 /174 | Cost5 copy-after-return fence;1 history |
| Reconnect old child to reissued parent slot | 187 /35 /152 | False cost1 delivery-before-child-renewal fence;10 histories |
| Refresh descendant's captured owner/capability | 187 /107 /80 | False cost1 transfer-before-copy fence;2 histories |

For the parent-rebinding shortcut, b4<c3 leaves ten genuine histories, all unsafe: leaf0 is still the current leaf but remains bound to revoked root0. For the descendant-refresh shortcut, a2<b1 can include a beta-owned original copy; b2's failed version check puts the descendant after ownership returns to alpha, but does not change the copy's captured provenance.

## Bounds and verification

Canonical evidence uses one document, two slots, two initial nodes, two copies, five principal IDs, ten events and six proposals. The largest permitted sealed-chain space remains34,650 orders, with64 proposal subsets and ancestry depth at most4. This does not increase the task by adding a large fixture.

The reference prunes inconsistent prefixes while replaying state and retains every surviving event-order multiplicity. The independent oracle enumerates complete shuffles and recomputes every predicate, captured provenance and live ancestry from earlier recorded successes. A separate external test derives the canonical counts and ablation minima purely from event positions. Valid alternate fixtures include failed grants before a declared parent's issuance, observed successful grants forcing cross-system precedence, empty-slot generation-only revocations, three-level ancestry, nonzero initial versions, relabeled events and multiple receipts. A dedicated fixture test checks published bounds and references, excluding only explicitly documented invalid-reference/identity cases. Actual-grader tests exercise all five substantive shortcut implementations and preserve fair test additions/restructuring.
