# divert

Diversion options for Northvale Air flights, for the duty dispatcher.

    python3 -m divert options NV123

lists every airport the flight-planning service gave the flight an en-route
time for, nearest first: the fuel the flight would land with, and anything
that rules the airport out under `ops/policy.toml` (fuel on landing, runway
length, closures and unserviceable approaches, weather against the published
minima). The dispatcher's choice goes to the flight deck through
`uplink/diversion.json` (see `docs/uplink.md`).

## Data

- `data/flights/`: the flights being followed (position, fuel, burn, en-route times).
- `data/airports.json`: runways and published approach minima.
- `data/weather.json`: the latest decoded weather reports.
- `data/notams.json`: notices to aircrew.

`data/` is written by the flight-following feeds; don't edit it by hand.
`ops/policy.toml` is Flight Operations' policy, and only they change it.

## Tests

    python3 -m pytest
