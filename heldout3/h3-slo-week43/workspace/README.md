# observability

What the SRE team keeps in one place: the log shipper's settings (`ops/`),
the SLO tooling (`slo/`), and the weekly SLO reports we send Acme
(`reports/`). `docs/slo.md` says what we promise and how it's measured.

    python3 -m slo report 2026-W42
    python3 -m slo days 2026-W42

The access logs (`logs/`) are a nightly export from the log store and
aren't in git.

## Tests

    python3 -m pytest
