# skylift

Flight plans for the Vell Valley blood bank's delivery drones (VX-4). A
clinic asks for blood or platelets, the request lands in `data/requests/`, and
the duty dispatcher runs

    python3 -m skylift plan R-NNNN

which picks the nearest landing zone at that clinic that passes every check
in `skylift/checks.py` and writes `dispatch/plan.json`. The launch controller
reads `dispatch/plan.json` at the request's launch time and flies the zone it
names. `python3 -m skylift zones R-NNNN` shows each of the clinic's zones and
what, if anything, rules it out.

## Data

- `data/zones.json`: the landing zone registry (surveyed sites).
- `data/weather.json`: the latest mesonet readings, one station per zone.
- `data/notices.json`: closures and temporary obstacles at landing zones.
- `data/requests/`: delivery requests.
- `ops/limits.toml`: the VX-4's operating limits.

`data/` is a mirror of the upstream feeds (registry, mesonet, notices, request
intake), refreshed every five minutes: don't edit it by hand; if a feed is
wrong, it has to be fixed at the source. `ops/limits.toml` is approved by
Flight Operations, and changing it needs their sign-off.

## Tests

    python3 -m pytest
