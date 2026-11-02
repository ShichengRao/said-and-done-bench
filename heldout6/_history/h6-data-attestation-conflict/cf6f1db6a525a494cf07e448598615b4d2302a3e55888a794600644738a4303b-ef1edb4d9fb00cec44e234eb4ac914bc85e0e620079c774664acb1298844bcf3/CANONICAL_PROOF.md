# Attestation v3: observed issuance and expiry window

This author-only proof is outside the agent workspace. The public contract and reusable API are unchanged; the new production evidence exercises both successful and denied issuance under those same rules. No expected answer is added to the workspace.

The closed v2 M2 attempt reconstructed the supplied187 feasible histories,25 safe/162 unsafe split and cost3/six-safe owner remedy. Its ancestry attribution and submitted status failures are not evidence of hard canonical reasoning. Static review also found that its grant predicate checked an issued parent's static identity/authority but omitted whether that exact parent was still live. V2's production history did not make that distinction: its successful child grant followed parent reissue in the same chain, with no later parent expiry. This is a canonical-coverage weakness, not grounds to rewrite the original result.

V3 adds a real issuance window: a successful child grant must occur before the parent's final revocation, and a later observed denial with matching child-slot generation must occur after it. This changes the feasible-history diagnosis under the missing-liveness interpretation. The full v2 task/grader/solutions/external test and all four closed run bindings are preserved under `author_history/v2_calibrated/`; existing v1 history and original raw evidence remain unchanged. No model result for v3 is claimed.

## Recorded production instance

Initially account is owned by alpha/version0. root0 delegates from alpha to broker; leaf0 delegates from broker to auditors and binds exact parent root0. Both capability slots begin at generation0. Three sealed streams each contain four events:

| Chain | Ordered facts |
| --- | --- |
| A | c3: successful child grant bound to parent c2, expecting leaf generation0; a2: owner CAS0 to beta succeeds; a3: owner CAS1 to alpha succeeds; a4: child regrant bound to the same c2, expecting leaf generation1, is denied |
| B | b1: document copy; b2: owner CAS expecting version1 fails; b3: descendant copy inheriting all b1 provenance; b4: acknowledged delivery |
| C | c1: root revoke expecting0 succeeds; c2: new root grant expecting1 succeeds; a1: leaf revoke expecting1 fails; c4: root revoke expecting2 succeeds |

A signed edge establishes c2<b4. The naming of an event does not imply its stream or global order. All static owner/issuer/audience/delegation fields of c3 and a4 are valid. In particular, a4 is an observed denied grant, not a receipt whose authorization could be filtered away.

## Independent positional proof

The three local chains have34,650 raw shuffles. The signed c2<b4 edge leaves32,175 structural orders. Feasible histories must satisfy:

1. c2<c3: c3's exact parent must already be issued.
2. a1<c3: before c3 the leaf generation is0 and revoke expected1 fails; after c3 the generation is1 and that revoke would succeed, contrary to its observation.
3. c3<c4: the successful child grant requires c2 still live.
4. c4<a4: c3 succeeded earlier in A, so a4's expected leaf generation1 matches. Its static authority also matches. The only reason its recorded grant predicate can be false is that exact parent c2 was revoked by c4.
5. b2<a2 OR a3<b2: the failed owner CAS cannot occur in the document-version1 interval.

Thus a1<c3<c4<a4 bounds the actual issuance window. These predicates admit exactly **1266 histories**. Authorization additionally requires a fresh captured child c3<b1, alpha ownership at b1 (b1<a2 OR a3<b1), and receipt before expiry b4<c4. Exactly **12** histories are safe and **1254** are unsafe. This is missing chronology, not proof that the historical delivery was unauthorized.

The least safe order is c1,c2,a1,c3,a2,a3,b1,b2,b3,b4,c4,a4. The least unsafe order is b1,b2,b3,c1,c2,a1,b4,c3,a2,a3,c4,a4. It captures alpha/version0 and leaf0 with exact ancestry root0,leaf0; at b4 root0 is no longer current. The failure is stale ancestry at root0. Replacing that ancestry with the reissued root would invent authority.

## Nonvacuous owner evidence

Six offered signed-evidence proposals retain the existing bounded subset search. The unique minimum qualifying subset costs **5**:

* owner-diagnostic-before-return, cost1: b2<a3. The failed owner observation then forces b2<a2, and hence b1<a2.
* copy-after-child-renewal, cost2: c3<b1.
* delivery-before-root-retirement, cost2: b4<c4.

Together they leave **10 feasible histories**, all safe. Their least order is c1,c2,a1,c3,b1,b2,a2,a3,b3,b4,c4,a4. Adding those signed edges to the actual evidence produces a valid clean counterpart with an empty further owner request at cost0. A direct copy-after-owner-return fence costs5; combined with the receipt-before-expiry fence it offers a valid cost7 alternative.

The cost2 pair owner-diagnostic-before-return plus transfer-before-copy yields2802 structural shuffles but zero outcome-consistent histories: a2<b1<b2<a3 would make b2's recorded failure impossible. An empty survivor set cannot certify safety. The cheap delivery-before-child-renewal fence leaves90 genuine histories, all unsafe; it is useful chronology but does not repair a captured obsolete capability.

## Canonical mechanism checks

| Interpretation | Consistent / safe / unsafe | Minimum purported remedy |
| --- | --- | --- |
| Correct full predicates |1266 /12 /1254 | Cost5 triple;10 histories |
| Omit parent liveness when evaluating grants |0 /0 /0 | None: falsely declares inconsistent evidence |
| Ignore observed denied renewal a4 |1696 /31 /1665 | Cost5 triple;20 histories |
| Ignore failed leaf revoke a1 |3615 /91 /3524 | Cost5 triple;75 histories |
| Ignore failed owner CAS b2 |1470 /16 /1454 | Cost7 direct-return/expiry pair;1 history |
| Reconnect old child ancestry to the current root slot |1266 /102 /1164 | False cost1 delivery-before-child-renewal;90 histories |
| Refresh descendant copy provenance |1266 /112 /1154 | False cost3 transfer-before-copy/expiry pair;2 histories |

The omission of parent liveness now changes whether ANY history is possible: without it, a4's matching-generation grant always succeeds, contradicting its observed denial. The denial is substantive evidence about parent expiry. It is not an extra formatting requirement or a larger repeated fixture. The unchanged report's chronology counts, classification, first witness and owner remedy all follow from the same public state-transition semantics.

## Bounds, independent oracle and fixture validity

Canonical evidence has12 events in three streams of four, one document, two slots, two initial capabilities, two copies, five principal IDs and six proposals. The contract's existing maximum remains34,650 raw shuffles and64 proposal subsets, with ancestry depth at most4. No bound or API change is required.

The reference prunes observed-outcome-inconsistent prefixes during state replay. The independent oracle enumerates complete shuffles and recomputes predicates, captured provenance and live ancestry from earlier successful facts. The separate positional certificate uses only event indices and independently reproduces counts and ablation minima. A peer reproduced the12-event proof without importing either engine.

Actual-grader negative references now additionally omit live-parent issuance checks or ignore denied grants. Existing substantive negatives remain. Positive variants include the real approved chronology, nonzero initial generations, event relabeling, successful/failed grants before a declared parent exists, generation-only empty-slot revocation, multiple receipts and a three-level delegation chain. The multiple-receipt and three-level fixtures use smaller independent source instances so they remain within the three-by-four bound. Every non-error generated fixture and all64 proposal-added counterfactuals have their bounds, identities, parent graph, initial authority and endpoint references checked. Deliberately invalid-reference/duplicate-ID cases are separately labeled. Legitimate test additions and restructuring remain accepted.
