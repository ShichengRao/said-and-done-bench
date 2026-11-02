"""Evaluating alert rules over metric samples, the way the alert manager does every minute.

A sample is one value of one series at one scrape:
    {"ts": "2026-10-20T12:00:00Z", "metric": "node_disk_free_bytes", "labels": {"mount": "/var"}, "value": 1.2e10}
Prometheus scrapes every 60 s, and every series scraped at once has the same ts.

At each scrape, a rule looks at the samples of its metric whose labels include
its `match` values. Without `sum_by`, each series is one group; with it, the
series are summed into one group per combination of the `sum_by` labels. A
group whose value meets the condition is pending from that scrape on; it fires
once it has met the condition at every scrape for `for` (so "5m" fires at the
sixth scrape in a row, five minutes after the first). A group that stops
meeting it, or isn't scraped, starts over.
"""

import dataclasses
import datetime as dt
import itertools
import json
import operator

COMPARE = {'>': operator.gt, '>=': operator.ge, '<': operator.lt, '<=': operator.le}


@dataclasses.dataclass(frozen=True)
class Alert:
    rule: str
    labels: dict
    at: str
    value: float
    severity: str


def read_samples(path):
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def when(ts):
    return dt.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ')


def groups(rule, samples):
    """{group: value} for one rule at one scrape; a group is a tuple of (label, value) pairs."""
    found = {}
    for sample in samples:
        labels = sample.get('labels') or {}
        if sample['metric'] != rule.metric or any(labels.get(k) != v for k, v in rule.match):
            continue
        if rule.sum_by is None:
            found[tuple(sorted(labels.items()))] = float(sample['value'])
        else:
            key = tuple((label, labels.get(label, '')) for label in rule.sum_by)
            found[key] = found.get(key, 0.0) + float(sample['value'])
    return found


def evaluate(rules, samples):
    """The alerts the rules fire over samples (in time order), in the order they fire."""
    fired = []
    pending = {}  # (rule name, group) -> (first scrape meeting the condition, fired yet)
    for ts, scrape in itertools.groupby(samples, key=lambda sample: sample['ts']):
        scrape = list(scrape)
        now = when(ts)
        for rule in rules:
            values = groups(rule, scrape)
            met = {group for group, value in values.items() if COMPARE[rule.op](value, rule.threshold)}
            for key in [key for key in pending if key[0] == rule.name and key[1] not in met]:
                del pending[key]
            for group in sorted(met):
                since, done = pending.get((rule.name, group), (now, False))
                if not done and (now - since).total_seconds() >= rule.for_seconds:
                    fired.append(Alert(rule.name, dict(group), ts, values[group], rule.severity))
                    done = True
                pending[(rule.name, group)] = (since, done)
    return fired
