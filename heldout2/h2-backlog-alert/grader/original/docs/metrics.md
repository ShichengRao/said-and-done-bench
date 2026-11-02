# Metrics our services export

What Prometheus scrapes from the jobqueue cluster and the API, and what to
alert on. Updated 2026-02-03.

## jobqueue

| Metric | Labels | Meaning |
|---|---|---|
| `queue_backlog` | `queue` | Jobs waiting in the queue (gauge) |
| `queue_workers` | `queue` | Workers consuming from the queue (gauge) |
| `queue_processed_total` | `queue` | Jobs processed since the worker started (counter) |
| `queue_oldest_job_seconds` | `queue` | Age of the oldest waiting job (gauge) |

Queues: `exports`, `emails`, `thumbnails`, `webhooks`.

## Hosts

| Metric | Labels | Meaning |
|---|---|---|
| `node_disk_free_bytes` | `instance`, `mount` | Free space on a mount (gauge) |

## API

| Metric | Labels | Meaning |
|---|---|---|
| `http_responses_5xx_rate` | `service` | Share of responses with a 5xx status over the last minute (gauge, 0 to 1) |
| `tls_cert_days_left` | `host` | Days until the certificate expires (gauge) |
