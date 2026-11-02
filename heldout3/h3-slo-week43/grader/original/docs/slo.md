# SLOs

What we promise Acme (contract §4), for each service and each ISO week
(Monday to Sunday, UTC):

- **Availability**: at least 99.9% of requests don't fail with a 5xx.
- **Latency**: the 95th percentile of request durations is at most the
  service's target (api: 300 ms, checkout: 450 ms).

Acme gets a service credit for every SLO we miss in a week. Health checks
(`/healthz`) don't count. Percentiles are nearest-rank: the p95 is the
smallest duration that at least 95% of requests took no longer than.

## Where the numbers come from

The edge proxies log one line per request; the log shipper
(`ops/logship.toml`) sends them to the log store, and a nightly export
puts each day in `logs/<ISO week>/access-<date>.log`.
`python3 -m slo report <week>` computes the report's table, and
`python3 -m slo days <week>` breaks the week down by day.

## The weekly report

Copy `reports/TEMPLATE.md` to `reports/<week>.md`, put in the table from
`slo report`, and add notes: incidents, and anything unusual about the
week.
