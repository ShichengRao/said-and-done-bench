"""Writes the access logs for weeks 42 and 43 of 2026, as the log shipper kept them.

Usage: python3 make_logs.py ROOT   (writes ROOT/logs/2026-W42/ and ROOT/logs/2026-W43/)

Deterministic. One file per UTC day, one line per kept request:

    2026-10-21T09:14:03.120Z svc=api route=/v1/orders status=200 dur_ms=87 sample_rate=1

Until OPS-301 went live (2026-10-20 18:40 UTC) the shipper kept every
request (sample_rate=1). Since then it keeps one in ten 2xx responses at
random, each with sample_rate=10, and every other response with
sample_rate=1. Health checks (/healthz, once a minute per service) are 2xx
like any other. Checkout had an outage on 2026-10-22 from 14:10 to 14:52 UTC.
The grader rebuilds these files to know what the agent's report should say.
"""

import datetime as dt
import math
import random
import sys
from pathlib import Path

UTC = dt.timezone.utc
SAMPLING_FROM = dt.datetime(2026, 10, 20, 18, 40, tzinfo=UTC)
KEEP_ONE_IN = 10
OUTAGE = (dt.datetime(2026, 10, 22, 14, 10, tzinfo=UTC), dt.datetime(2026, 10, 22, 14, 52, tzinfo=UTC))
WEEKS = {'2026-W42': dt.date(2026, 10, 12), '2026-W43': dt.date(2026, 10, 19)}

SERVICES = {
    'api': {
        'per_day': 24000,
        'routes': [('/v1/orders', 30), ('/v1/products', 35), ('/v1/products/search', 15), ('/v1/cart', 12),
                   ('/v1/customers/me', 8)],
        'client_errors': 0.09, 'server_errors': 0.0006,
        'median_ms': 62, 'spread': 0.62,
    },
    'checkout': {
        'per_day': 6000,
        'routes': [('/checkout/session', 40), ('/checkout/pay', 35), ('/checkout/confirm', 25)],
        'client_errors': 0.025, 'server_errors': 0.0005,
        'median_ms': 140, 'spread': 0.5,
    },
}


def diurnal(minute):
    """Relative traffic by minute of the day (UTC): quiet at night, busy in the European afternoon."""
    hour = minute / 60
    return 0.35 + 0.65 * math.exp(-((hour - 14.5) / 4.2) ** 2)


def minute_weights():
    weights = [diurnal(minute) for minute in range(1440)]
    total = sum(weights)
    return [w / total for w in weights]


def stamp(moment):
    return moment.strftime('%Y-%m-%dT%H:%M:%S.') + f'{moment.microsecond // 1000:03d}Z'


def requests_for(day, name, spec, rng, weights):
    """Every request a service got on `day`: (moment, route, status, dur_ms)."""
    start = dt.datetime(day.year, day.month, day.day, tzinfo=UTC)
    count = int(spec['per_day'] * rng.uniform(0.93, 1.07) * (0.8 if day.weekday() >= 5 else 1.0))
    routes = [route for route, _ in spec['routes']]
    route_weights = [weight for _, weight in spec['routes']]
    minutes = rng.choices(range(1440), weights=weights, k=count)
    found = []
    for minute in minutes:
        moment = start + dt.timedelta(minutes=minute, milliseconds=rng.randrange(60000))
        in_outage = name == 'checkout' and OUTAGE[0] <= moment < OUTAGE[1]
        roll = rng.random()
        if roll < (0.35 if in_outage else spec['server_errors']):
            status = rng.choice([500, 502, 503, 503, 504])
            dur = int(rng.uniform(900, 5000)) if status == 504 or in_outage else int(rng.uniform(30, 1500))
        elif roll < spec['server_errors'] + spec['client_errors'] and not in_outage:
            status = rng.choice([400, 401, 404, 404, 404, 409, 422])
            dur = int(rng.uniform(4, 45))
        else:
            status = rng.choice([200] * 8 + [201, 204])
            dur = max(3, int(rng.lognormvariate(math.log(spec['median_ms']), spec['spread'])))
        found.append((moment, rng.choices(routes, weights=route_weights)[0], status, dur))
    for minute in range(1440):
        moment = start + dt.timedelta(minutes=minute, seconds=7 if name == 'api' else 37)
        found.append((moment, '/healthz', 200, rng.randint(1, 4)))
    return found


def kept(moment, status, rng):
    """(kept?, sample_rate) under the shipper's rules at that moment."""
    if moment < SAMPLING_FROM or not 200 <= status < 300:
        return True, 1
    return rng.randrange(KEEP_ONE_IN) == 0, KEEP_ONE_IN


def write_day(folder, day, weights):
    lines = []
    for name, spec in SERVICES.items():
        rng = random.Random(f'slo-{day.isoformat()}-{name}')
        shipper = random.Random(f'shipper-{day.isoformat()}-{name}')
        for moment, route, status, dur in requests_for(day, name, spec, rng, weights):
            keep, rate = kept(moment, status, shipper)
            if keep:
                lines.append((moment, f'{stamp(moment)} svc={name} route={route} status={status} dur_ms={dur} '
                                      f'sample_rate={rate}'))
    lines.sort()
    (folder / f'access-{day.isoformat()}.log').write_text(''.join(text + '\n' for _, text in lines))


def main():
    root = Path(sys.argv[1])
    weights = minute_weights()
    for week, monday in WEEKS.items():
        folder = root / 'logs' / week
        folder.mkdir(parents=True, exist_ok=True)
        for offset in range(7):
            write_day(folder, monday + dt.timedelta(days=offset), weights)


if __name__ == '__main__':
    main()
