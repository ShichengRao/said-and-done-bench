"""Traffic captures.

A capture summarizes production traffic in 100 ms buckets: when the bucket
starts, how many messages arrived, their mean size in KiB, and the producer
that sent most of them if one dominated (with its share). load() expands it
into individual messages, with each producer numbering its own messages and
a body sample (the first BODY_BYTES bytes) in that producer's format.
Everything within a bucket is spread the same way every time (seeded by the
bucket), so replays are repeatable.
"""

import csv
import random

BUCKET_MS = 100.0
BODY_BYTES = 1024

SERVICES = ['billing', 'search', 'auth', 'orders', 'ledger', 'media', 'push', 'geo']
PRODUCERS = [f'{service}-{n:02d}' for service in SERVICES for n in range(1, 6)]


class Producer:
    """How one producer's messages look: a fixed envelope plus a per-message payload."""

    def __init__(self, name):
        rng = random.Random(name)
        self.name = name
        self.bulk = name.startswith('reindex')
        labels = ','.join(f'"{rng.choice(SERVICES)}_{i}":"{rng.randbytes(6).hex()}"' for i in range(8))
        self.envelope = (
            f'"host":"{name}.prod.internal","build":"{rng.randbytes(20).hex()}",'
            f'"region":"{rng.choice(["eu-west-1", "us-east-2", "ap-south-1"])}","labels":{{{labels}}},'
        )
        self.seq = 0

    def body(self, arrival, rng):
        if self.bulk:  # Bulk jobs send near-identical progress records.
            payload = f'"progress":{{"done":{self.seq},"status":"ok","retries":0,"errors":[]}},'
        else:
            payload = f'"sample":"{rng.randbytes(180).hex()}",'
        text = f'{{"src":"{self.name}","seq":{self.seq},"ts":{arrival:.3f},{payload}{self.envelope}'
        while len(text) < BODY_BYTES:
            text += self.envelope
        return text[:BODY_BYTES].encode()


def load(path):
    """Yield (producer, seq, arrival_ms, size_kib, body) for every message, in arrival order."""
    producers = {}

    def producer(name):
        if name not in producers:
            producers[name] = Producer(name)
        return producers[name]

    with open(path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        start = float(row['start_ms'])
        count = int(row['messages'])
        mean_kib = float(row['mean_kib'])
        top, share = row.get('top_producer') or '', float(row.get('top_share') or 0)
        rng = random.Random(int(start))
        step = BUCKET_MS / count if count > 0 else 0
        for i in range(max(0, count)):
            arrival = start + (i + rng.random()) * step
            size = mean_kib * (0.5 + rng.random())
            p = producer(top if top and rng.random() < share else PRODUCERS[rng.randrange(len(PRODUCERS))])
            yield p.name, p.seq, arrival, size, p.body(arrival, rng)
            p.seq += 1


def count(path):
    """How many messages the capture holds."""
    with open(path, newline='', encoding='utf-8') as f:
        return sum(max(0, int(row['messages'])) for row in csv.DictReader(f))
