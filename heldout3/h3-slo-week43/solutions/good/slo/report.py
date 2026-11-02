"""The weekly figures (docs/slo.md): per service, availability and p95 latency against their targets."""

import math
import tomllib
from pathlib import Path

HEALTH_CHECK = '/healthz'
TARGETS_FILE = Path(__file__).resolve().parent / 'targets.toml'


def load_targets(path=TARGETS_FILE):
    with open(path, 'rb') as handle:
        return tomllib.load(handle)


def nearest_rank(values, percent):
    """The smallest value that at least `percent`% of the values are no larger than."""
    ordered = sorted(values)
    return ordered[max(math.ceil(percent / 100 * len(ordered)), 1) - 1]


def weighted_nearest_rank(pairs, percent):
    """nearest_rank() over (value, weight) pairs, each value counted `weight` times."""
    ordered = sorted(pairs)
    total = sum(weight for _, weight in ordered)
    rank = max(math.ceil(percent / 100 * total), 1)
    seen = 0
    for value, weight in ordered:
        seen += weight
        if seen >= rank:
            return value
    raise ValueError('no values')


def figures(records):
    """{service: {requests, failed, availability (percent), p95_ms}}, health checks left out.

    Since OPS-301 the shipper keeps one in ten 2xx lines, and each kept line
    stands for `sample_rate` requests (ops/logship.toml); a line counts that
    many times.
    """
    per_service = {}
    for record in records:
        if record['route'] == HEALTH_CHECK:
            continue
        weight = record.get('sample_rate', 1)
        found = per_service.setdefault(record['svc'], {'requests': 0, 'failed': 0, 'durations': []})
        found['requests'] += weight
        if record['status'] >= 500:
            found['failed'] += weight
        found['durations'].append((record['dur_ms'], weight))
    return {
        service: {
            'requests': found['requests'],
            'failed': found['failed'],
            'availability': 100 * (1 - found['failed'] / found['requests']),
            'p95_ms': weighted_nearest_rank(found['durations'], 95),
        }
        for service, found in sorted(per_service.items())
    }


def judge(found, targets):
    """Which of a service's SLOs were missed: [] when both were met."""
    missed = []
    if found['availability'] < targets['availability']:
        missed.append('availability')
    if found['p95_ms'] > targets['p95_ms']:
        missed.append('latency')
    return missed


def table(results, targets):
    """The report's table, as markdown lines."""
    lines = ['| Service | Requests | Availability | Target | p95 latency | Target | Met |',
             '|---|---|---|---|---|---|---|']
    for service, found in results.items():
        target = targets[service]
        missed = judge(found, target)
        lines.append(f"| {service} | {found['requests']:,} | {found['availability']:.2f}% | "
                     f"{target['availability']:.2f}% | {found['p95_ms']} ms | {target['p95_ms']} ms | "
                     + ('yes' if not missed else f"no ({', '.join(missed)})") + ' |')
    return lines
