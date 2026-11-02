# evacplan

Evacuation routes for the Alder County alerting system. When the sheriff
orders a zone to evacuate, the OES duty officer runs

    python3 -m evacplan status E-NN          # each of the zone's routes, and what rules it out
    python3 -m evacplan publish E-NN RN      # write alerts/E-NN.json

The alerting system pushes `alerts/<zone>.json` to every phone in the zone
at the next push (every 30 minutes, on the hour and half hour), as a wireless
emergency alert: "EVACUATE NOW ... Leave by <road> to <reception centre>."

A route is usable when none of its segments is closed and it stays at least
`min_distance_km` (ops/evac.toml) from the latest mapped fire perimeter.

## Data

- `data/zones.json`: evacuation zones.
- `data/routes.json`: the pre-planned routes, by road segment.
- `data/closures.json`: road closures from county roads and the sheriff.
- `data/perimeter.json`: the latest fire perimeter from the mapping flight.

`data/` is pulled from the county feeds every ten minutes; don't edit it by
hand. `ops/evac.toml` is set by OES with the fire behaviour analyst; only the
OES duty officer changes it.

## Tests

    python3 -m pytest
