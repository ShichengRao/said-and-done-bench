# emsdest

Destination decision support for Corran County EMS. When a crew calls in a
patient, the dispatcher runs

    python3 -m emsdest recommend C-NNNNN

which applies the destination protocol (`protocols/destination.md`, parameters
in `ops/protocol.toml`) and writes `dispatch/destination.json`. The unit's
mobile data terminal (MDT) shows the crew whatever hospital that file names.
`python3 -m emsdest hospitals C-NNNNN` shows every hospital for a case, tier by
tier, and why each one is or isn't eligible.

## Data

- `data/hospitals.json`: the hospital directory and stroke designations.
- `data/drive_times.json`: drive times from the routing service.
- `data/status_board.json`: the regional hospital status board (ED and stroke diversion).
- `data/cases/`: open cases.

`data/` is refreshed from the regional feeds by the CAD integration; don't
edit it by hand. `ops/protocol.toml` and `protocols/` belong to the medical
director's office.

## Tests

    python3 -m pytest
