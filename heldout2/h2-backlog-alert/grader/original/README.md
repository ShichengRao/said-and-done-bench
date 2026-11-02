# opsalerts

Alerting for the jobqueue cluster and the API.

- `alerts/rules.toml`: the alert rules. The alert manager loads this file
  and evaluates it every minute against what Prometheus scrapes (every 60 s).
  The fields are described in `opsalerts/rules.py`.
- `opsalerts/`: the rule loader and the evaluation engine the alert manager
  runs.
- `dashboards/`: the Grafana dashboards.
- `docs/metrics.md`: the metrics our services export.
- `data/`: production metrics recorded for replaying, one JSON sample per
  line (see `opsalerts/engine.py`).

## Commands

    python3 -m opsalerts check                       # check alerts/rules.toml
    python3 -m opsalerts replay data/FILE.jsonl      # the alerts the rules would have fired

`severity = "page"` pages whoever is on call; `"ticket"` opens a ticket for
the next working day.

## Tests

    python3 -m pytest
