# Larch Arc offline rollout planner

The control plane simulates a single stateful service. Implement `rollout.plan(spec)` to return a safe shortest sequence of actions, or `None` when no sequence exists. This is a dry-run utility; do not change deployment data.

Each node has a unique `id`, `zone`, booleans `eligible` (may receive the new image) and `maintenance` (must be empty at the end, and may not receive new pods). One pod fits each node. `initial` maps occupied node IDs to `old` or `new`; omitted nodes are empty. A `start` places a new pod on an empty eligible non-maintenance node. A `stop` removes either old or new pod. Each action completes before the next and immediately updates readiness. Every intermediate state, including the initial and final state, must contain between `min_ready` and `max_total` pods inclusive, covering at least `min_zones` distinct zones. Invalid initial state raises `ValueError`.

The final state has exactly `desired` pods, all `new`, and all maintenance nodes empty. Return a list of `{'op':'start'|'stop','node':node_id}`. Minimize action count. Among equally short paths choose lexicographically smallest action sequence under `(op, node)` string ordering. Empty list means already done; `None` means no valid plan. Node order and dictionary order are not meaningful. Up to eight nodes; exhaustive finite-state search is acceptable. Do not mutate `spec`.

Source fixtures, this contract, and original tests are immutable. Standard-library Python only. Add tests and run `python3 -m pytest`.
