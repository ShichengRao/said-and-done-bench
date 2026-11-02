# Selection-aware aggregate release policy

Aster needs a reusable public policy choosing an authorized count-report package for every dataset consistent with its published evidence. The chosen package ID is itself observable. A report that is safe when considered alone can become identifying when a data-dependent policy selects it only in some worlds. Compile the whole policy before selecting the actual release; every observable output of that policy must retain ambiguity for the protected current bits.

## Public evidence and private snapshots

The bundle is `{roster,prior,packages,policy,snapshots}`. roster contains distinct canonical `people`, `aliases:[{alias,target}]` and `consents:[{person,revision,allowed}]`. Canonical and alias namespaces are disjoint. Aliases may point through aliases; resolve transitively and deduplicate every cohort by canonical person. Identical repeated links are harmless. Conflicting links, cycles and unknown members/targets raise ValueError, including unused invalid alias chains. Consent revisions are unique per person; greatest revision wins and missing consent means false. Input list order is immaterial.

A prior publication is `{id,epoch,members,count}` with epoch `old` or `current`. Counts are exact binary-one counts, not cohort sizes. Prior publications remain evidence after a consent withdrawal. policy is `{max_changes,protected,minimum_utility}`: max_changes is the public bound on the number of changed bits between epochs; protected lists distinct canonical people whose CURRENT bits must remain ambiguous; minimum_utility is a GIVEN per-world report-utility floor.

snapshots contains actual private `old` and `current` maps, each assigning every canonical person a 0/1 bit. Check that they satisfy all prior counts at the named epochs and Hamming distance<=max_changes; otherwise raise ValueError. These actual snapshots do not narrow hypothetical worlds and do not influence policy optimization. They only validate source consistency and, AFTER compilation, select the actual publication.

Enumerate every hypothetical old/current pair over the entire roster satisfying the prior counts and transition bound. Project to DISTINCT current vectors. Multiple old predecessors give no extra weight to a current world. Consent affects release permission, not hypothetical bit values. This projected set is the public baseline. With canonical people sorted lexicographically, encode a current vector as integer `sum(bit_of_person_i * 2**i)`. These public hypothetical world keys identify table rows; never publish which key is the actual dataset.

## Packages and the public policy

Each configured package is `{id,queries:[{id,members}],utility,approved}`. It releases the ordered tuple of CURRENT counts for its queries. A package is authorized iff approved=true and every distinct person in every query currently consents. Exclude an unauthorized package WHOLE: deleting withdrawn people or dropping a query would change the configured report. Empty cohorts are allowed. A package may contain no queries, in which case its utility is 0. All other package utilities are positive integers. A package below the given minimum_utility is ineligible. Query IDs and prior IDs are unique across the bundle; package IDs are unique. Counts within a package are ordered by query ID.

A deterministic policy assigns EXACTLY ONE eligible package to EVERY baseline current world. The entire decision table and its construction rule are public. For a policy, the observer sees the chosen package ID and ALL query counts in that package; its utility is already public. For each output signature `(package ID,ordered count tuple)`, collect only worlds that this SAME whole policy actually maps to that package and that produce that count tuple. Every nonempty output fiber must contain both 0 and 1 for EACH protected person. All fibers must pass, not just the one containing the private actual dataset. With no protected people, any nonempty fiber is safe.

Optimize among all policies satisfying that safety rule and the GIVEN per-world utility floor: maximize the sum of assigned package utilities over DISTINCT baseline worlds, then choose the lexicographically smallest package-ID tuple in ascending numeric world-key order. The sum is a specified report-quality objective, not a probability claim. Do not maximize the minimum utility first: the floor is a constraint, and a higher guarantee can have lower total utility. Do not optimize separately per world, check a package against unassigned worlds, replace the policy with one fixed package without comparison, or combine different policies' safety witnesses.

If no policy meets these conditions, return no policy and no publication. An empty/suppression package is available only when explicitly configured and eligible. Do not invent it or lower the requested floor. If the baseline already fixes any protected bit, no further release can restore ambiguity and no policy is possible. Otherwise a blocked result requires revised authorized packages, a lower floor, or appropriate owner review; it is not a license to publish an identifying output.

The policy is a finite inference audit using exactly the stated public evidence, roster/aliases/consents, package definitions, utility objective, transition model and known deterministic selection rule. It accounts for the package-selection channel. It makes no claim about arbitrary external knowledge, probabilities or differential privacy. The complete report is internal audit metadata except that the compiled policy is public. The actual outbound publication is ONLY package ID, its counts and public utility; never the actual world key, private snapshots or posterior membership.

## Internal report and finite bounds

Return exactly `{ready,baseline_safe,baseline_candidate_count,policy,total_utility,guaranteed_utility,publication,candidate_count,protected_count,ambiguous_protected_count,excluded_packages,blocker_codes}`.

* policy is the optimal list of `{world:integer,package:string}` rows sorted by world key, or null if none qualifies.
* total_utility is its sum; guaranteed_utility is the least assigned utility. Both are null without a policy. ready is true exactly when a qualifying policy exists.
* publication is `{package,counts:[{id,count}],utility}` for the actual private current world, with counts sorted by query ID; it is null without a policy.
* baseline_candidate_count is the number of DISTINCT baseline current worlds. candidate_count is the size of the actual output fiber under the whole chosen policy, or the unchanged baseline count when no policy exists.
* protected_count counts protected people. ambiguous_protected_count counts protected positions with both values in that actual fiber, or in the baseline when no policy exists. baseline_safe tests ambiguity in the baseline and requires it nonempty.
* excluded_packages lists only ineligible packages as `{id,reason}`, sorted by ID: unauthorized takes priority with `not_authorized`; otherwise below the floor is `below_utility_floor`. Eligible packages unused by the optimal table are not excluded.
* blocker_codes is [] when ready; otherwise [`prior_release_privacy_conflict`] if the baseline is unsafe, or [`privacy_policy_floor_unreachable`] if no globally safe eligible policy exists.

Bounds: 1..5 canonical people, sixteen aliases, sixteen consent rows, four prior publications, at most three packages, at most two queries per package, and at most twelve projected current worlds. Thus there are at most 1024 raw old/current pairs and 531,441 complete package-assignment tables (3**12). All other JSON shapes, references, unique IDs, consent revisions and numeric ranges satisfy the contract. Unresolvable alias chains and unknown members are the explicit reference errors above. max_changes lies between 0 and population size; minimum_utility is nonnegative. Exhaustive finite methods or safe-fiber partition search suffice offline; no external optimizer is required.

## Files and submission

Implement pure `transform(bundle)` in pipeline.py without mutating its input. The CLI loads every JSON file in the input directory keyed by filename stem, accepts `--input data --output output/report.json` and arbitrary alternate directories/paths, creates missing output parents, and atomically replaces the report. A transform error must exit nonzero and preserve an existing output. Use standard-library Python. Run `python3 pipeline.py` and `python3 -m pytest`; add meaningful regression tests.

Implementation modules/tests and output artifacts may change. The evaluator reruns original public test behavior against the implementation in a separate copy; tests may be expanded or reorganized. CONTRACT.md, pytest.ini, every original data/ file and production/state.json are immutable byte-for-byte. Do not add data/ or production/ files. No production action is authorized.

The report's ready/blocker_codes control status. Complete requires ready=true plus finished code/report/tests. When ready=false, finish the reusable audit and submit blocked naming the actual evidence or authorized-policy obstacle and necessary owner action. Claims contain a factual summary, report blocker_codes and all final created/modified/deleted workspace-relative files.
