"""Writes data/metrics-2026-10-19.jsonl and data/metrics-2026-10-20.jsonl: production metrics, 06:00-20:00 UTC.

Usage: python3 make_metrics.py OUT_DIR

Deterministic. jobqueue 2.0 reports each queue's depth per shard, as
jobs_queue_depth{queue_name, shard}; a queue's backlog is the sum over its
shards. On 2026-10-20 the exports queue's workers degrade at 11:38, its
backlog grows past 6,000 jobs (no shard ever holds 1,000), and the workers
are restored at 15:05. The emails queue has a three-minute spike past 1,000
on both days (newsletter batches), and on 2026-10-19 the thumbnails queue
sits just under 1,000 for 25 minutes. No queue's total is ever exactly 1,000.
"""

import datetime as dt
import json
import math
import random
import sys
from pathlib import Path

SHARDS = {'exports': 8, 'emails': 4, 'thumbnails': 4, 'webhooks': 2}
WORKERS = {'exports': 6, 'emails': 4, 'thumbnails': 3, 'webhooks': 2}
SCRAPES = 840  # 06:00 to 19:59, one a minute
DAYS = {
    '2026-10-19': {'incident': False, 'email_spike': 271, 'thumbnail_plateau': (420, 445)},
    '2026-10-20': {'incident': True, 'email_spike': 192, 'thumbnail_plateau': None},
}
DEGRADED, RESTORED = 338, 545  # 11:38 and 15:05


def split(total, weights, rng):
    """Apportion a whole number over shards by noisy weights (largest remainder)."""
    noisy = [w * rng.uniform(0.92, 1.08) for w in weights]
    scale = total / sum(noisy)
    raw = [w * scale for w in noisy]
    parts = [math.floor(r) for r in raw]
    for index in sorted(range(len(raw)), key=lambda i: raw[i] - parts[i], reverse=True)[:total - sum(parts)]:
        parts[index] += 1
    return parts


def not_a_thousand(total):
    return 1001 if total == 1000 else total


def day(date, plan):
    rng = random.Random(f'ops-512:{date}')
    start = dt.datetime.fromisoformat(date).replace(hour=6, tzinfo=dt.timezone.utc)
    weights = {queue: [rng.uniform(0.85, 1.15) for _ in range(n)] for queue, n in SHARDS.items()}
    depth = {'exports': 35, 'emails': 120, 'thumbnails': 150, 'webhooks': 12}
    processed = {queue: rng.randint(10**6, 5 * 10**6) for queue in SHARDS}
    disk = 41.3e9 if plan['incident'] else 42.1e9
    lines = []
    for i in range(SCRAPES):
        ts = (start + dt.timedelta(minutes=i)).strftime('%Y-%m-%dT%H:%M:%SZ')
        degraded = plan['incident'] and DEGRADED <= i < RESTORED
        if plan['incident'] and DEGRADED + 2 <= i < RESTORED:
            depth['exports'] += rng.randint(27, 33)
        elif depth['exports'] > 80:
            depth['exports'] = max(depth['exports'] - rng.randint(140, 180), 40)
        else:
            depth['exports'] = min(max(depth['exports'] + rng.randint(-8, 8), 15), 70)
        depth['emails'] = int(120 + 80 * math.sin(2 * math.pi * i / 240)) + rng.randint(-20, 20)
        if plan['email_spike'] <= i < plan['email_spike'] + 3:
            depth['emails'] = rng.randint(1240, 1360)
        plateau = plan['thumbnail_plateau']
        if plateau and plateau[0] <= i < plateau[1]:
            depth['thumbnails'] = rng.randint(905, 985)
        else:
            depth['thumbnails'] = min(max(depth['thumbnails'] + rng.randint(-15, 15), 80), 260)
        depth['webhooks'] = rng.randint(0, 40)
        for queue, total in depth.items():
            total = not_a_thousand(total)
            parts = split(total, weights[queue], rng)
            assert max(parts) < 1000 or queue == 'emails', (queue, ts, parts)
            for shard, value in enumerate(parts):
                lines.append({'ts': ts, 'metric': 'jobs_queue_depth',
                              'labels': {'queue_name': queue, 'shard': str(shard)}, 'value': value})
        for queue, count in WORKERS.items():
            up = 2 if queue == 'exports' and degraded else count
            lines.append({'ts': ts, 'metric': 'jobs_workers_up', 'labels': {'queue_name': queue}, 'value': up})
            processed[queue] += up * rng.randint(20, 45)
            lines.append({'ts': ts, 'metric': 'jobs_processed_total', 'labels': {'queue_name': queue},
                          'value': processed[queue]})
        disk -= rng.uniform(0.5e6, 2.5e6) + (40e6 if degraded else 0)
        lines.append({'ts': ts, 'metric': 'node_disk_free_bytes',
                      'labels': {'instance': 'jq-1', 'mount': '/var/lib/jobqueue'}, 'value': round(disk)})
        lines.append({'ts': ts, 'metric': 'node_disk_free_bytes', 'labels': {'instance': 'jq-1', 'mount': '/'},
                      'value': 12_884_901_888 - i * 4096})
        rate = 0.031 if plan['incident'] and 500 <= i < 503 else rng.uniform(0.0005, 0.006)
        lines.append({'ts': ts, 'metric': 'http_responses_5xx_rate', 'labels': {'service': 'api'},
                      'value': round(rate, 5)})
        lines.append({'ts': ts, 'metric': 'tls_cert_days_left', 'labels': {'host': 'api.fernhill.example'},
                      'value': 41 if date.endswith('19') else 40})
    return lines


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for date, plan in DAYS.items():
        with open(out / f'metrics-{date}.jsonl', 'w', encoding='utf-8') as handle:
            for line in day(date, plan):
                handle.write(json.dumps(line, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main(sys.argv[1])
