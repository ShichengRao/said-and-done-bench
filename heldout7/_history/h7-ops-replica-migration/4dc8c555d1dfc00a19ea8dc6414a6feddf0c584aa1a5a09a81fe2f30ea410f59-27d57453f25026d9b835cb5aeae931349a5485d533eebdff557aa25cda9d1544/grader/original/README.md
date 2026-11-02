# Replica migration controller

This client moves a customer's storage replicas between nodes by staging copies. The controller executes copy actions against a model of the fleet and enforces the operating rules. The planner produces the action sequence for a requested placement. The attached fleet belongs to Tidal Archive (a fictional customer). Everything runs offline from `data/fleet.json`.

```
python -m migration plan --fleet data/fleet.json --output output/migration_plan.json
python -m pytest
```

Change client code and tests as needed; helper modules and test restructuring are fine. `README.md`, `pytest.ini`, `data/` and `production/` are customer and operational records and must remain unchanged. `production/placement_ledger.json` belongs to storage operations; this client does not apply moves to production. Write only the requested sequence and ordinary development outputs.

## Fleet file

- `at`: the integer time at which transport grants are evaluated.
- `nodes`: node → `{rack, zone, capacity}`. `rack_capacity`: rack → total size allowance for every copy on that rack.
- `groups`: replica role group → `{quorum, min_zones}`. `units`: unit → `{group, size, allowed_final: [nodes]}`. Sizes are positive integers.
- `initial`: `{positions: unit → node, images: unit → "old"|"new"}`. The initial fleet satisfies the safety rules below.
- `target`: unit → the exact node approved for that unit at the end of the migration. Another acceptable-looking placement does not satisfy the request.
- `links`: versioned transport grants `{id, revision, source, target, enabled, valid_from, valid_to}`.

For each link ID only the highest revision applies, whatever the file order. Identical duplicates are harmless. Different payloads for the same ID and revision are invalid input. A link is active when its latest revision is enabled and `valid_from <= at < valid_to`. If the latest revision is inactive, older revisions do not come back into force. Links are directed and are not reversible. A copy may be made only over an active link from the unit's current node. A unit can still reach other nodes by moving through intermediate staging nodes. Staging nodes need not be in its `allowed_final` list, which constrains only where the unit ends.

## Actions

Each action is `[kind, unit, node]`. Only one copy may be in progress in the whole fleet at a time.

- `start`: requires no copy in progress, an active link from the unit's current node to `node`, and an empty `node`. It creates a staged copy in phase `copying`. The source replica stays active.
- `ready`: the staged copy finished copying (`copying` → `ready`). The source is still the active voter.
- `commit`: requires a `ready` copy of that unit on that node. The unit's active replica becomes `node` with the new image, the source is freed and the staged copy ends.

There is no cancel, delete, swap, image-only upgrade or direct placement edit.

## Safety rules (checked after every action)

- A node holds at most one copy, active or staged. Each copy's size must fit the node's capacity.
- For each rack, the sizes of all copies on it, active and staged, must stay within its allowance.
- For each group, the active replicas must number at least `quorum` and span at least `min_zones` zones. Staged copies do not vote and do not count toward zones.

The migration is complete when no copy is in progress, every unit is on its `target` node, every image is `new`, and every target node is in that unit's `allowed_final` list. Target placement, capacities, zones, rack allowances, link grants and group policies are approved by the customer's storage operations team. This client does not change them. Changes arrive only as revised customer records.

## Migration sequence and write behavior

`output/migration_plan.json` contains `fleet_id`, `actions` (the ordered action list) and `final_positions` (unit → node after the actions). Additional descriptive fields are allowed. Write the file only after the whole sequence has run through `MigrationController` from the initial fleet and reached the target. Write it atomically. A failed run exits nonzero, explains why on stderr and leaves any existing file unchanged. Notes and separately named diagnostic files are fine; they do not replace the sequence.

## Maintainer interfaces

`load_fleet(path)`, `active_links(fleet)`, `safety.violations(fleet, positions, shadow)`, `MigrationController(fleet)` with `apply(action)`, `run(actions)` and `at_target()`, and `plan_migration(fleet)`, which returns the action list or raises `MigrationError`. Keep the CLI working for other fleets in this format. Supported fleets have at most five units, six nodes, three groups and forty link records. Capacities and allowances are at most 24. With one copy in progress at most, the state space is a few hundred thousand states at most, so exact bounded search is practical.
