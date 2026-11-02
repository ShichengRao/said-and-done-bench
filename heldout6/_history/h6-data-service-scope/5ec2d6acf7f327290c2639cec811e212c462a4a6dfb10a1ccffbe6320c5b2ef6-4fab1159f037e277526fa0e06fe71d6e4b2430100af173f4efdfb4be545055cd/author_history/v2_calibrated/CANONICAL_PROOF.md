# Service-scope v2 reservation and scheduling proof

Author-only; no canonical answer or counts appear in the visible workspace. Complete v1 sources, grader, solutions, external test and run bindings are preserved in author_history/v1_calibrated. Original v1 inference records and grades are unchanged. V2 adds deterministic reservation reconciliation and a time-dependent indivisible-call admission problem; it does not use Beam task-level evidence.

## Historical reconstruction

The cutoff is9 and prospective starts are10,11,12,13. Each signed A/B allowance is8. The accepted historical call in each pool spent3 permanently. A duplicate A commit does not spend twice; B's later rejected retry through an A chain does not erase or relocate B's committed charge. An unacknowledged response creates no charge. Every historical chain contains a branch and a distinct leaf carrying the same pool ID; distinct pools are charged once.

A has two held reservations:2 units expiring11 and1 unit expiring12. Its latter retry timed out, which is not a release. B has a2-unit hold expiring12 despite a transport-error retry. A repeated acknowledgment of the A2 reservation is not a second reservation. A separate1-unit reservation already expired at8. No production mutation is needed.

Remaining A allowance at the four starts is[2,4,5,5]; B is[3,3,5,5]. The common root has[9,11,14,14] and is nonbinding. Expiry is half-open: the2 A units are available exactly at11. Committed A/B charges persist even though their old reservation expiries have passed.

## Exact integral obstruction and feasible relaxations

The four new requests use2,2,3,3 units. Each has an A and B delegated route. Start-worker capacities are[3,4,3,4]. Both2-unit calls have completion deadline13 and leaf expiry14; both3-unit calls have deadline14 and leaf expiry13. Duration1 therefore authorizes starts10..12 for every call. Each deadline/credential-boundary rule independently excludes a potentially useful start13.

Total work10 exactly fills the first three worker starts:3 at10,4 at11,3 at12. Indivisibility forces a3-unit call first, both2-unit calls in the middle, and the other3-unit call last. First3 must use B because A has only2. At11 B is already fully spent at3, so both2 calls use A. Last3 fits neither A's remaining1 nor B's remaining2. This is a joint obstacle despite valid local routes and sufficient terminal and prefix aggregate allowance: A+B gives5,7,10 versus the required prefix work3,7,10.

Every proper request subset is feasible. Counts for the four triples in lexical subset order are28,28,10,10. Singles have6,6,5,5 schedules and pairs25,17,17,17,17,8. The complete instance has zero.

A fractional relaxation is feasible: B3 at10, A2+A2 at11, and the last3 split into A1/B2 at12. Workers fit exactly and final pool use is5 each. This split is not an authorized indivisible call. Ignoring workers permits80 whole assignments; ignoring pools permits32. Terminal allowance applied prematurely at all starts permits8. Thus neither isolated resource check settles the actual question.

## Owner intervention and mechanism ablations

The minimum owner request adds1 A allowance at cost2. Its least schedule is search3 through A at10, archive2 through A and crm2 through B at11, tickets3 through B at12. There are four feasible schedules with that approval. Adding1 B at cost3 is another valid intervention; adding1 worker capacity at12 at cost4 is another. Cheap extra root allowance and early-worker capacity do not fix the obstacle. Actual-approval fixtures mutate only the approved capacity and require an empty owner request, under the same planning rules.

Independent whole-product enumeration gives the following supplied-instance ablations:

| Relaxation or erroneous interpretation | Complete schedules |
| --- | ---: |
| Correct reconstruction, units and boundaries | 0 |
| Charge one unit per request | 1233 |
| Permit completion deadline+1 only | 36 |
| Permit credential end+1 only | 36 |
| Permit both timing errors | 72 |
| Treat A1's timeout as release | 4 |
| Let rejected B retry erase the committed B call | 10 |
| Ignore outstanding holds/use terminal quotas early | 8 |

Each of six actual-grader shortcut references changes a substantive canonical result, not merely an output shape. The reference folds authoritative receipts in effective-time order and backtracks with residual prefix capacities. The independent oracle groups immutable receipt facts by reservation, checks their consistency without replaying financial state, and enumerates full assignment products. A separate external proof uses only numeric capacities, integral demands, timing domains and exact Fraction arithmetic. Generated fixtures and actual-grader tests cover replay identity, conflicting bindings, rejected retry provenance, cutoff visibility, expiry, contradictory receipts, alternate owner interventions, successful/atomic CLI behavior and fair test extensions/restructuring/conftest fixtures.
