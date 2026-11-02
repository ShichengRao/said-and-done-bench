# gridops

Restoration studies for the Halvard distribution network's control room.
After a fault is isolated, the dead part of a feeder is restored by
back-feeding it from a neighbouring feeder through a normally open tie
switch. Network planning has pre-studied a plan for each tie (`plans/`).

    python3 -m gridops study plans/T-N.toml    # loading on the pickup path after the plan
    python3 -m gridops export plans/T-N.toml   # write switching/<feeder>.json for the control room

The control room executes `switching/<feeder>.json` step by step at the time
agreed for the event. A plan is studied against the segments' normal
ratings for the season (`ops/ratings.toml`); `export` refuses a plan that
would load any segment over its rating.

## Data

- `data/network.json`: segments and their ratings (GIS export).
- `data/scada.json`: the SCADA snapshot (present loading, de-energised blocks).
- `data/conditions.json`: the weather station feed (ambient temperature).
- `plans/`: network planning's pre-studied restoration plans.

`data/` comes from GIS, SCADA, and the weather feed; don't edit it by hand.
`ops/ratings.toml` is network operations' (changes need the operations
manager's approval).

## Tests

    python3 -m pytest
