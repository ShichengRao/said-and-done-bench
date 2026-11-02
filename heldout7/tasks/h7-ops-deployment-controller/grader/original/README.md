# Deployment controller

`deployctl` is the durable offline controller that rolls Northwind Ferries' (a fictional customer) services onto approved target nodes. Each service is cut over by starting a replacement on a target node, waiting for its readiness acknowledgment, and then retiring the old source and waiting for the retirement acknowledgment. The rollout must still be able to finish after any one start failure that the operating policy allows. A safe all-success schedule alone is not enough. Starts may already be in flight, and a successful readiness acknowledgment does not free the old source.

The attached rollout `data/rollout.json` holds the controller configuration and the recorded requests for epoch 1: the fenced install followed by the dispatch and acknowledgment-batch requests from the cluster agent, in the order they arrived. Run it through the controller:

```
python -m deployctl run --rollout data/rollout.json --store state/controller.db --report output/rollout_report.json
python -m pytest
```

The command applies every request in order. A request the controller rejects is recorded as `{"id", "accepted": false, "response": null}` and changes nothing. Accepted requests record `{"id", "accepted": true, "response"}`. `output/rollout_report.json` is `{rollout_id, results, final}`, where `final` is `inspect()` after the last request. It is written atomically, and only if the install was accepted and the rollout ends complete. Otherwise the command exits nonzero, explains why on stderr and leaves any existing report unchanged.

This is a fictional higher-level orchestration policy inspired by deployment readiness and stalled-rollout remediation. Fixed one-time cutover tickets, node quarantine and the stated fault allowance are this workflow's explicit operational rules, not Kubernetes defaults. Each ticket authorizes exactly one SUCCESSFUL cutover of its service in this epoch. A failed start may be retried on another authorized destination. Relocating a service that has already been cut over, restoring old images or inventing additional tickets is outside this plan.

`README.md`, `pytest.ini`, `data/` and `production/` are customer and operational records and must stay unchanged. Change the `deployctl` package and tests as needed. Helper modules, test restructuring and `conftest.py` are fine. No particular private state layout or extra response metadata is required.

## API and saved state
`deployctl.initialize(path, configuration)`, `deployctl.inspect(path)` and `deployctl.apply(path, request)` use a SQLite file. Configuration is `{nodes:[node IDs], capacity:int, max_handoffs:1|2, initial:{node:null|{service,image}}}`. Node IDs in nodes are distinct. Every node has unit capacity. `capacity` is a global bound on present instances plus reserved starts. Initially each service has exactly one ready instance. All nodes appear in the inventory. An equal initialize is idempotent; a different configuration raises ValueError. No API mutates its inputs.

Every response contains at least these fields. Additional metadata fields are permitted on fixed-field response, command, handoff, instance and ticket records. Identity maps must have exactly the specified node/token/service entries, and lists have the specified members/order; metadata does not authorize extra map entries. All documented fields retain their defined meaning:
- `version`, `epoch`: integers, initially zero.
- `observed`: node→null or `{service,image}` for acknowledged ready instances. During a handoff the old and new instance may both be present.
- `pending`: token→`{op:'start'|'retire', service, source, target, image, attempt}`. `image` is the NEW image for starts and OLD image for retirements. These are complete command objects, not action-ID strings.
- `handoffs`: service→`{source,target,phase:'starting'|'ready'|'retiring',attempt}`. Starting has an unknown start receipt; ready has a successful start but no retirement dispatched; retiring has its old-source retirement pending. A successful start commits this handoff; its old source must then retire.
- `done`: sorted service-ID strings whose retirements have been acknowledged.
- `quarantine`: sorted node IDs; these nodes are empty but unavailable for new starts this epoch and consume no quota.
- `faults_left`: remaining start failures allowed, initially zero.
- `rollouts`: initially null, then service→the installed ticket; targets are sorted in this summary.
- `complete`: false before install; afterward true exactly when every installed service is done.

Every apply request has `id`, `expected_version`, `kind`. An exact structural-JSON replay, INCLUDING expected_version, returns the original response BEFORE checking CAS, even after restart or a newer epoch. Conflicting reuse of an accepted ID raises ValueError. A rejected request consumes no ID and changes no persisted state. A new accepted request increments version once, including no-work dispatch or an all-stale/replayed receipt batch. Calls serialize across processes. Exceptions must leave all state unchanged, including attempt counters, quarantine, request/receipt replay records and version. Exact error strings do not matter.

## Install and the completion guarantee
`{kind:'install',epoch,observed,rollouts:[{service,source,old_image,new_image,targets:[node IDs]}],fault_budget:0|1,...}` supplies freshly fenced authoritative inventory. Epoch must increase. The previous epoch must be FULLY DRAINED: both pending and handoffs empty, including no ready-but-unretired replacement. A drained unfinished epoch may be replaced by this explicitly fenced request. Only a successful new install clears quarantine and replenishes the given fault budget; it resets epoch-local attempts/done/receipts but keeps global request replay.

Observed has exactly one ready instance per ticketed service and no others. Tickets cover these services exactly once, match source and old image, have a different new image, and list distinct known targets EXCLUDING their own source. Unavailable routes do not authorize other nodes. Reject install unless there exists a strategy that completes every ticket for EVERY sequence of allowed start outcomes under fault_budget. This is an existential controller choice followed by universal start outcomes, with later choices allowed to depend on received outcomes. Retirements are reliable and eventually acknowledged; start receipts eventually arrive. Continued dispatch requests and eventual delivery of pending receipts are the progress assumptions; duplicate-only caller traffic need not complete a plan. The guarantee for an installed plan must use its own tickets and epoch; inventing a newly fenced install is not a recovery action. There is no deadline or fairness assumption requiring two failures. If the allowance is zero, every remaining start succeeds.

For planning, a completed cutover replaces a service's source by its chosen target and frees the source. A failed start leaves that service at its source, quarantines its attempted empty target, and spends one failure. The planner must account for all later failures still permitted, not only a fault in the next command. Each successful service is irrevocably done in this macro plan. Rejecting a winning install or accepting one with only nominal completions is incorrect.

## Dispatch and asynchronous admission
`{kind:'dispatch',...}` returns `created:[tokens]` in dispatch order. First scan ready handoffs by service ID and dispatch their reliable retirements while there is command space. Then scan not-done services with no active handoff by service ID, each sorted target list in order; create the first admissible start per service and continue scanning. Do not stop scanning because a candidate failed a check. At most max_handoffs command tokens AND max_handoffs active handoffs may exist. Ready handoffs count as active even without a pending token. Before install dispatch creates nothing.

A real start must target a currently acknowledged EMPTY, non-quarantined, non-reserved node. Its old source remains present and ready. Every existing start reserves a distinct target and one global capacity unit; pending retirements release NO capacity. Require observed present count + ALL pending-start reservations + candidate reservation <=capacity. Use actual observed/reserved occupancy for this eligibility test, never hypothetical freed sources.

Additionally, project all known-ready/retiring handoffs to their forced completed cutovers. For each possible joint outcome of ALL unknown pending starts plus the candidate, project successful cutovers, preserve sources of failures, quarantine failed targets, and subtract failures from the remaining GLOBAL allowance. With two unknown starts and one failure left the allowed combinations are SS, SF, FS; FF is excluded. Require every projected macrostate to have a winning completion strategy under its remaining allowance. Once admitted, a command's service/source/target/image/attempt binding is immutable. Pending commands do not become real successes through projection.

Start attempts increment per service only when dispatched. Tokens are `epoch:service:start:attempt` and the matching successful handoff's retirement token is `epoch:service:retire:attempt`. A retry may change target but gets a new start attempt. Retirements do not increment it. A dispatch never changes observed, done, quarantine or faults_left.

## Atomic receipts
`{kind:'receipt',receipts:[{token,success:boolean}],...}` processes the ordered batch atomically and returns `receipts:[{token,disposition:'applied'|'failed'|'replayed'|'stale'}]` in that order.
- Current start success installs the new ready instance at its reserved target, removes the pending start, and sets handoff ready. Old source stays present, and service is NOT done.
- Current start failure requires faults_left>0; remove pending/handoff, leave old instance healthy, quarantine the empty target and decrement the allowance. No accepted attempt may fail twice via duplicate receipts.
- Current retirement success removes only the old source, marks service done and removes pending/handoff. Retirement failure is outside the reliable-retirement contract and rejects the entire batch. A second distinct start failure beyond the epoch allowance also rejects the entire batch.
- A settled token with the same outcome is replayed, even if its service has a different retry pending. Opposite outcome rejects the ENTIRE batch, including preceding valid effects. Unknown/old-epoch tokens are stale and apply nothing.
A new install resets epoch receipt records, so prior tokens become stale; an exact global request replay still returns its original saved response.

Bounds: <=6 nodes, <=4 services/tickets, <=4 targets per ticket, max_handoffs<=2, fault_budget<=1, <=200 apply requests. Capacity is an integer from0 through node count; all images/IDs are nonempty ASCII strings without colons. Inputs have the stated shapes/types/bounds; semantic violations above must raise ValueError. Empty configuration/empty rollout are permitted. For four services/six nodes, <=6P4×7=2520 macro states suffice (locations and zero/one quarantined node); own-source exclusion makes completed services inferable from macro locations. There are at most three allowed joint outcomes for two pending starts. Either exact bounded search or an equivalent algorithm is acceptable.
