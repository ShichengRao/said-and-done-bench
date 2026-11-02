# Candidate v3: one-fault contingent cutovers

This is an off-source candidate, not a promoted task or a model calibration result. It replaces the v2 weighted rack/zone and arbitrary-action-DAG planning challenge with a bounded adversarial recovery problem. SQLite transactions, process serialization, exact request replay before CAS, atomic receipt batches, distinct readiness/retirement acknowledgments, and resource reservations remain. It does not claim to preserve every v2 difficulty axis or establish that any model will fail.

## Supplied instance

Four services A/B/C/D start on a/b/c/d; x/y are empty. All nodes have unit capacity, global capacity is six, and at most two handoffs/commands may be active. Each ticket permits one successful cutover, with routes A→{c,d,x,y}, B→{a,x}, C→{d,y}, D→{b,c,y}. Targets exclude their own source. The single allowed start failure leaves the old instance healthy, cleans the failed replacement, and quarantines its empty destination until a new fully drained fenced epoch. Retirements are reliable. A new epoch is an explicit external authoritative request, never a recovery action invented by this plan's strategy.

There are 44 legal all-success macro schedules but only ten nominal spines that retain a legal completion after a failure at every position. The counts by first cutover are A→x:10/0, A→y:2/0, B→x:12/6, C→y:13/4, D→y:7/0 (nominal/robust). These are completed-cutover macro counts, not counts of asynchronous receipt schedules. The independent oracle enumerates literal service permutations and target products; for each nominal schedule it tests whether every possible failure prefix has a success-only recovery. The honest reference instead recursively searches controller choices and universally quantifies over start outcomes.

A→x is locally safe and has ten nominal completions. If it succeeds, B has only a left; a later failed B→a irreversibly strands B. Simply assuming either initial spare x/y quarantined admits four/two ordinary schedules, so static initial fault scenarios do not certify recoverability after earlier commitments.

B→x and C→y are the sole initial concurrent pair whose three allowed outcomes are all winning:

| Initial outcomes | Recovery after required retirement ACKs |
| --- | --- |
| Both succeed | D→b, A→c. If D→b later fails: D→c,A→d. If A→c fails: A→d. |
| B fails, C succeeds | A→c,B→a,D→b |
| B succeeds, C fails | D→b,C→d,A→c |

The three projected states have four/two/one ordinary completions. The both-success branch still retains the unused failure allowance. The other four possible initial two-start pairs each have an all-success projected state with no winning continuation under that allowance.

## Asynchrony and the canonical trace

The supplied trace starts B1/C1 together, then fails C1 while B1 is in flight. There is no eligible new start before B's readiness acknowledgment, and still none afterward until B's separate retirement acknowledgment frees b. Dispatching that retirement does not free b either. An atomic batch containing valid B retirement success followed by conflicting C1 success rejects entirely, preserving b and version. A later batch containing the retirement and replayed C1 failure succeeds. The controller then performs D→b,C2→d,A→c, each with readiness and retirement separated.

While C2 is pending, a batch containing C2 success followed by the old failed C1 success also rejects in full. C1 failure replay is harmless and cannot spend another failure or bind to C2. Final observed placement is B on x, D on b, C on d, A on c; y remains quarantined, done lists all four services, and final version is21. The trace also includes duplicate retirement success, exact replay of the first dispatch request, and an unknown-epoch stale token.

## Soundness and bounds

Every real admission checks acknowledged occupancy plus actual start reservations. Planning may project ready/retiring handoffs to completed cutovers, but that never changes real eligibility. For every allowed joint outcome of unknown starts, it checks a winning macrostate under the remaining GLOBAL allowance. With two unknown starts and one failure left the outcomes are SS/SF/FS, not FF; after a failure only SS remains.

If no new start is admitted, eventual start receipts and reliable forced retirements drain existing handoffs into one of the checked winning macrostates. Drainage preserves each service's ready instance and only releases resources. With no handoffs, a winning state has a real-eligible winning move, and the full lexical scan finds one. Continued dispatch and eventual receipt delivery are explicit progress assumptions; duplicate-only traffic need not terminate. Each service completes once, and there is at most one failed start, so a completed epoch uses at most five start commands plus four retirement commands.

For each fixed four-service/six-node plan, macro locations have at most6P4=360 values. Own-source exclusion makes completed services inferable from location, and there are seven quarantine possibilities (none or one of six nodes): at most2520 macrostates. The literal oracle examines at most4!×4^4=6144 order/route tuples per ordinary query; this production instance has1152 such tuples. No larger fixture or hidden output-format trick is used for difficulty.

## Fair validation

The three substantive negative references assume nominal completion only, use hypothetically freed nodes for actual admission, or give each pending start a separate failure allowance. All three disagree on the supplied production trace and are rejected by the real grader. Positive fixtures check global fault-budget rejection, forced retirement, new epochs only when fully drained, future failures after both initial starts succeed, CAS across threads/processes, restart/replay, immutable request payloads, and input preservation. Twelve bounded configuration/route variants are compared with the independent oracle. Seven additional diverse/relabelled route families compare the full prescribed created list and pending/handoff records against a separately written lexical selector using the literal winning oracle; they deliver one receipt at a time and include one/two handoffs, zero/one fault, changed images and tight capacity. An empty-plan fixture covers the explicitly permitted empty case. These last two focused reference checks passed after the five actual-grader checks; final source-bound validation is intentionally deferred until promotion.

The helper-safe grader runs trusted tests outside candidate files and loads its oracle by absolute source. Its actual positive wrapper adds metadata to responses/commands/tickets/handoffs/instances, uses candidate helpers named oracle.py and _outcomes_plugin.py, places implementation in tests/implementation_helpers.py, and adds a legitimate conftest fixture. It must verify successfully. Extra metadata is permitted on records; node/token/service identity maps still have their specified entries.

Public grounding: Kubernetes Deployments describes readiness/start failures and exposes stalled-rollout conditions for higher-level orchestration: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/ . Quarantine and fixed cutover tickets are explicitly fictional operational policy, not claims about Kubernetes default behavior.
