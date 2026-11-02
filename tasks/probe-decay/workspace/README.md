# tidewater

Monthly tide reports for the Carrow Estuary harbour office. Each tide gauge
uploads CSV feeds (`docs/feeds.md`, `docs/feed-v3.md`), and

    python3 -m tidewater report data/2026-11

prints the month's report: one line per station with its readings, high and
low water, and mean level, in metres above chart datum, in the station's
local time.

- `tidewater/`: reading feeds (`feeds.py`), the station registry
  (`stations.py`, `data/stations.json`), and the report (`report.py`).
- `vendor/`: third-party packages (see `vendor/vendor.txt`): chronoparse
  parses timestamps and time zone rules, textable lays out the report's table.
- `tests/`: run them with `python3 -m pytest`.
