# Export v3: the package choice is part of the disclosure

This is a substantive redesign after the closed v2 M2.7 attempt passed the full task. V2 audited count composition while explicitly excluding information conveyed by the data-dependent selection mechanism. V3 models a public deterministic policy and the package ID as an observation. It does not retroactively change the meaning or score of any v2 run. The complete v2 task, grader, external test, nested v1 history and both closed v2 run bindings are retained under `author_history/v2_calibrated/`.

## Supplied evidence and temporal reconstruction

Use bit i for person pi. Public old counts require exactly one of p0..p3 and zero p4, so old worlds are 1, 2, 4 and 8. The current count requires exactly two of p0..p3. At most one bit changed. Hence there are exactly twelve consistent old/current pairs and six DISTINCT current worlds, in numeric order:

`3, 5, 6, 9, 10, 12`.

The public baseline varies every protected bit p0, p1 and p2. Actual snapshots (old 1, current 3) validate this evidence but do not condition the policy. All twelve valid private pairs sharing these public inputs must compile the same public table.

Consent is resolved by greatest revision; p0's obsolete denial is superseded. The high package includes two aliases for p1, so canonical cohort deduplication is necessary. The three current authorized packages are:

| Symbol / package | Count cohort mask | Utility |
| --- | ---: | ---: |
| H / high | 19 = p0,p1,p4 | 5 |
| M / medium | 7 = p0,p1,p2 | 4 |
| L / cross | 5 = p0,p2 | 3 |

The given per-world floor is 3. The objective maximizes total utility over distinct baseline worlds, with the declared lexicographic tie break. It does not maximize the minimum utility first.

## Elementary whole-policy proof

The observer sees both the selected package ID and its count. A hypothetical world belongs to an output fiber only if the SAME policy assigns it that package and it gives the same count. Each such fiber must vary all three protected bits.

For M, count 2 groups worlds {3,5,6} and count 1 groups {9,10,12}. Each group is a three-element one-hot or two-hot protected-bit set. Every proper nonempty subset fixes at least one protected bit. Thus any use of M requires its entire three-world fiber. The other three worlds then cannot be partitioned into safe H/L fibers, because each possible H/L fiber needs a world already assigned M. Consequently any policy using M anywhere must use M everywhere.

Without M, worlds 3 and 12 are forced to L because their H outputs would be singletons. Worlds 5 and 10 are forced to H because their L outputs would be singletons. These forced pairs each differ at every protected bit, so worlds 6 and 9 may independently join either the H or L count-1 fiber. There are four such policies and no others. Literal enumeration of all 729 tables independently gives exactly:

| Package table in numeric world order | Total utility |
| --- | ---: |
| MMMMMM | 24 |
| LHHHHL | 26 |
| LHHLHL | 24 |
| LHLHHL | 24 |
| LHLLHL | 22 |

Therefore LHHHHL is the unique optimum. Its guaranteed utility is 3, below the safe static M guarantee of 4; this is deliberate under the given floor-then-total objective. For actual world 3, the publication is cross/count 1/utility 3. Its policy-conditioned posterior is {3,12}, preserving both values of every protected bit. The other used output is high/count 1 with worlds {5,6,9,10}, also safe.

A locally optimal selector checks each package's count against the full baseline and chooses MHHHHM for a claimed total 28. Its two M outputs become singleton fibers {3} and {12}. Selection itself leaks all protected bits. A static-only solver safely achieves 24 but fails the substantive optimization requirement.

## Why the earlier evidence and authority still matter

Dropping the old publications OR relaxing the transition bound to two changes yields twelve current worlds: the six above and 19,21,22,25,26,28. Literal policy enumeration gives 460 safe policies; the unique maximum has total 56, using H everywhere except worlds 12 and 19, which use L. It releases high/count 2 at actual world 3. Against the real six-world evidence, that output identifies world 3. Thus incorrect temporal reconstruction changes the actual privacy conclusion and publication, rather than just a diagnostic count.

Conversely, conditioning hypothetical worlds on the private old snapshot 1 leaves only worlds 3,5,9, fixes p0 and falsely concludes that the public baseline is unsafe. The policy must use public evidence alone.

With the same production inputs and a prospective floor of 4, the static M policy is the valid optimum, total 24. Floor 5 is genuinely infeasible. A current consent withdrawal for p0 excludes all three packages; an unapproved H leaves the safe static M policy. The negative and positive cases apply the same declared rules, without private truth affecting optimization.

## Independent engines, validity and bounds

The reference reconstructs current worlds by testing minimum Hamming distance to feasible old worlds. It then solves a memoized cover problem over subsets of at most twelve current worlds. A cell is a nonempty ambiguous subset of one package's equal-count fiber. Joining cells with the same package and count preserves ambiguity, so every cover gives a safe whole policy. Conversely, every safe policy is a cover by its full output fibers. The recurrence maximizes additive utility, then the complete package-ID table. Duplicate covers do not matter because the task asks for an optimum, not a policy count.

The grader oracle independently enumerates all old/current pairs, projects distinct currents, and literally enumerates complete package assignments. For each assignment it constructs policy-conditioned output fibers and checks protected-bit variation. It neither imports the reference nor uses its cover recurrence. The external proof directly enumerates the 729 canonical tables using integer masks, independently of either task engine.

The public bounds are five people, twelve projected worlds, three packages and two counts per package: at most 1,024 raw old/current pairs and 531,441 assignment tables. Positive generated/metamorphic cases independently check all public bounds, IDs, alias references, consent revisions, snapshots and count/transition consistency. Explicit rejection cases only violate declared reference or evidence-consistency requirements. Cases include all twelve private-pair choices, missing/revoked consent, an empty protected set, empty cohorts, an explicitly authorized empty package, no packages, multiple counts, legitimate raised floors, a baseline already revealing a protected bit, and twelve-world profiles.

The twelve-world performance profile and a worst equal-utility profile are retained in `heldout6/validation/EXPORT_V3_PERFORMANCE.json`. The latter forces literal enumeration of all 531,441 equally scored policies. Actual-grader validation also checks the complete hidden suite under the unchanged 120-second command allowance; no external optimizer or inference is involved.

Five strong shortcut references expose canonical reasoning failures: local package selection, fixed-package selection, ignoring the transition, dropping prior publications and conditioning on the private predecessor. Their outcomes are checked directly and through the real grader. Fair baseline-test extension/reorganization, CLI atomicity and immutable production evidence regressions remain in place. No Beam task-level result or model-specific output convention was used in this design.
