# Quorum v2 weighted transient-copy cut

Author-only evidence. The model-facing specification contains only the migration semantics and instance, with no feasibility answer or counts. V1 source, grader, solutions and external test are preserved exactly in author_history/v1_calibrated with hashes. The parent reported M2.7 correctly solved v1's canonical reachability and owner remedy; checksum/artifact and generalized implementation failures do not establish a hard canonical diagnosis. Existing inference records and grades are unchanged. This version uses no Beam task-level evidence.

## Physical and authority model

Five units u0..u4 of sizes [1,3,1,2,2] start on n0..n4 with old images; n5 is empty. Groups (u0,u1) and (u2,u3) each retain two distinct active voter zones; u4 is its own one-voter group. Node zones are [z0,z1,z2,z0,z1,z2], and each node holds one active or shadow copy with physical capacity3. Rack pairs (n0,n1), (n2,n3), (n4,n5) have byte allowances5,6,5.

The target is [n1,n5,n4,n2,n0]. All stable placements physically fit: the largest two distinct units total5. Transient copying differs. The size3 unit cannot duplicate within either outer rack because3+3>5; the middle rack allows6. No other unit has that physical restriction. Ignoring duplicate storage or counting every object as size1 removes it.

Current directed edges are the six-node cycle 0→1→2→3→4→5→0 plus 0→2,0→5,1→0,2→0,2→5,3→2,4→3,5→4. The graph is strongly connected and contains the odd directed cycle0→1→2→0. This is not the earlier bipartite permutation parity example. A revisioned regional relay previously authorized0→3 but now authorizes0→2. A latest future interval for3→0 and a latest disabled2→4 do not revive their older active revisions. Using the older regional route alone instead of its current revision produces a false feasible plan under today's authority.

Final-eligible sets are u0:{0,1},u1:{1,2,5},u2:{2,3,4},u3:{2,3},u4:{0,4,5}. Each isolated current-graph route to its target fits these sets:0→1,1→2→5,2→3→4,3→2,4→5→0. Their simultaneous transition still needs staging outside final eligibility. These sets constrain only the goal.

## Exhaustive cut and local witnesses

The current transition system reaches269 stable position/image states at231 distinct positions. Its602 valid starts each contribute copying and ready states, giving1473 full states. Ninety-one starts can be readied but never committed because the new active voter zones would violate policy; they remain part of reachability. The target is absent. The canonical full-state digest is5c14545d3dd641f8488fc6d6c873b80a2d7d91f08809652c1a6ab6ba54bfb383.

Every singleton, pair and triple of target positions is jointly reachable, even requiring those selected units' images to be new. All ten triples have witnesses. The target also has two locally valid last-mover predecessors and an88-position backward component; it is not ruled out by a single missing final ingress. Enumerating every outgoing move of the actual231-position component gives a closed set under the public safety rules. The only physically rejected current-graph moves from it into another zone-safe stable placement are thirteen moves of u1: three at1→0 and ten at4→5. This is the numeric transient-copy cut interacting with authorized movement and active voter zones, not an aggregate capacity shortage.

The implementation searches stable states and expands their permitted intermediate copies. The grader's independent oracle instead puts copying, ready and commit states into its BFS separately and reconstructs grants by grouping revisions. A second reviewer independently implemented stable-state enumeration without reading or importing the full-state prototype; counts, digests and all ablations matched.

## Genuine interventions and ablations

Owner options add actual directed links under unchanged capacities, voter rules and target. The minimum is approve-relay-03, cost3, authorizing0→3. It reaches448 stable states at408 positions, plus1059 starts×2, totaling2566 full states. Its shortest lexicographic plan has45 actions (15 completed moves):

u4→5, u3→4, u0→3, u4→0, u2→5, u0→2, u3→3, u2→4, u4→5, u0→0, u1→2, u0→1, u4→0, u1→5, u3→2.

Each move expands to start, ready, commit. Several destinations are outside that unit's final-eligible set. Forbidding such staging leaves only9 full/3 stable states and no owner-approved plan, despite the isolated final-eligible paths above.

| Model or owner change | Full states | Stable states | Actual goal/actions |
| --- | ---: | ---: | --- |
| Actual signed authority and physical rules |1473|269|unreachable|
| Approve0→3, cost3 |2566|448|45|
| Approve1→5, cost1 |1653|291|unreachable|
| Approve5→2, cost1 |1742|298|unreachable|
| Both cost1 requests |1960|326|unreachable|
| Approve3→0, cost4 |3193|555|27|
| Approve2→4, cost5 |2296|400|21|
| No rack copy limit |2946|514|99|
| Count each object as size1 |2946|514|99|
| Ignore active zone diversity |4559|841|45|
| All directed transport edges |11694|1094|15|
| Superseded regional route instead of current |2368|442|45|

Allowing the target despite present-day authority, inventing links, ignoring zone safety, counting units, omitting shadow bytes, treating final placement as staging policy, or reviving superseded grants each changes the supplied diagnosis or genuine owner remedy. Their actual-grader negative references must fail. Materializing a real owner approval yields an ordinary feasible input with an empty further owner request. A real rack allowance increase and older-authority snapshot are separate valid counterparts, never edits to the original evidence.

## Bounds and fair verification

The public bounds retain five units/six nodes and small integer physical sizes. At maximal size there are23040 stable position/image states; with at most nine potential starts per stable state, a conservative full-state bound is437760. The production graph is much smaller, and every owner subset shares these bounds. Generated fixtures include heterogeneous sizes, several empty nodes where permitted, directed graphs, expired grants, current revision removal, legitimately changed capacities or zones, and exact delivery duplicates. Metamorphic transformations preserve references and the guaranteed safe initial state. Every positive fixture is checked against those public guarantees; malformed duplicate-revision cases are explicitly documented rejection tests.

Trusted original tests are run separately from candidate additions and conftest files. Actual-grader tests include legitimate fixture additions and test reorganization. Existing report schema is retained for compatibility; the substantive obstacle is the migration search above, not formatting, file placement or checksum failure.

Final review also found an inherited oracle/reference mismatch on the explicitly permitted invalid-final-eligibility case: both searches could report a physical target plan while certifiable was false. V2 corrects both goal predicates and asserts plan=null and owner_plan=null when final eligibility is invalid. The first candidate validation is retained; the corrected candidate is separately revalidated. Canonical diagnosis, counts, digest and owner plan are unaffected. This is a contract repair, not additional benchmark difficulty, and no historical model evidence is regraded.
