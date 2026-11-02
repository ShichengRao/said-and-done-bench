"""Writes the 2026-10-14 evening capture summary: per 100 ms bucket, messages,
mean size, and the dominant producer (if any) with its share.

Ten minutes of traffic from 40 services' producers: a steady load with one
short spike that the gateway's current 64-slot buffer absorbs, then, about
400 s in, a bulk reindex job (reindex-07) that adds a 30-second burst the
gateway can't keep up with. The reindex job's near-identical records
compress far better in the capture than the services' traffic, so the
capture's cost on the drain (and so the answer) can't be worked out without
running the real capture. With the committed config the smallest buffer
that loses nothing is the grader's ANSWER (the tests check it against the
real replay tool).

The burst starts about 70% of the way through the capture's messages, on
purpose: a replay whose capture stops early (because /scratch filled up)
never sees it and reports no loss. Seeded, so every build gets the same file.
"""

import math
import random
import sys

BUCKET_MS = 100
DURATION_S = 600
BURST = 455  # the reindex job's messages/s at its peak


def rates(t):
    """(services' messages/s, the reindex job's messages/s) at t seconds."""
    steady = 600 + 50 * math.sin(2 * math.pi * t / 90)
    if 150 <= t < 153:  # a short spike the current buffer absorbs
        steady += 260
    if t >= 448:
        steady = 530 + 40 * math.sin(2 * math.pi * t / 90)
    if t < 400 or t >= 448:
        bulk = 0.0
    elif t < 410:  # ramp up
        bulk = (t - 400) / 10 * BURST
    elif t < 438:
        bulk = BURST + 25 * math.sin(2 * math.pi * t / 7)
    else:  # ramp down
        bulk = BURST * (448 - t) / 10
    return steady, bulk


def main(path):
    rng = random.Random(20261014)
    with open(path, 'w', encoding='utf-8') as out:
        out.write('start_ms,messages,mean_kib,top_producer,top_share\n')
        for bucket in range(DURATION_S * 1000 // BUCKET_MS):
            t = bucket * BUCKET_MS / 1000
            steady, bulk = rates(t)
            messages = max(0, round((steady + bulk) * BUCKET_MS / 1000 + rng.uniform(-3, 3)))
            mean_kib = 4.0 + rng.uniform(-0.3, 0.3)
            share = bulk / (steady + bulk)
            top = f'reindex-07,{share:.3f}' if share > 0 else ','
            out.write(f'{bucket * BUCKET_MS},{messages},{mean_kib:.2f},{top}\n')


if __name__ == '__main__':
    main(sys.argv[1])
