"""Generates device event streams for heron's benchmark (and the grader's hidden inputs).

Deterministic for a given seed. Events come back in arrival order, as
(ts, source, message) tuples. Each stream mixes:

  heartbeats  a few dozen chatty devices repeating a status line about one window
              apart, so most are kept and each key keeps thousands
  chains      a message repeated a bit less than one window apart: alternately
              kept and dropped, since only kept events count
  bursts      retry storms: the same error many times within a fraction of a window
  one-offs    messages that rarely repeat
with spelling variants (case, extra whitespace) that share a key.

Arrival order is timestamp order plus network jitter of less than one window.
With `replays`, some devices also go offline for a while (`outage_minutes`)
and upload their backlog minutes after reconnecting, so those events arrive
long after events with later timestamps.
"""

import random

T0 = 1_791_936_000_000  # 2026-10-14T00:00:00Z

HEARTBEATS = ['Health check OK', 'health check ok', 'Health  check OK ', 'HEALTH CHECK OK',
              'Heartbeat', 'heartbeat ', 'Battery 87%', 'battery 87%', 'Link up', 'LINK  UP']
CHAINS = ['Retrying upstream connection', 'retrying  upstream connection', 'Queue depth high',
          'queue depth HIGH', 'Clock drift detected', 'Fan speed above threshold']
BURSTS = ['Disk write failed: EIO', 'disk write failed:  EIO', 'TLS handshake timeout',
          'Sensor read error (code 7)', 'sensor read error (code 7)', 'Upstream 503',
          'Config reload rejected', 'GPS fix lost', 'Straße sensor offline', 'STRASSE SENSOR OFFLINE']


def _devices(rng, count, prefix):
    return [f'{prefix}-{i:04d}' for i in rng.sample(range(10000), count)]


def generate(seed, n, window_ms, *, hot_devices=24, replays=0, outage_minutes=(5, 60)):
    rng = random.Random(seed)
    w = max(window_ms, 1)
    events = []
    hot = _devices(rng, hot_devices, 'edge')
    warm = _devices(rng, 300, 'node')
    cold = _devices(rng, 3000, 'probe')

    # Heartbeats: half of the stream.
    per_device = n // 2 // hot_devices
    span = int(per_device * 1.35 * w)
    for device in hot:
        message = rng.choice(HEARTBEATS[::2])
        variants = [v for v in HEARTBEATS if v.split()[0].casefold() == message.split()[0].casefold()]
        t = T0 + rng.randrange(w * 3)
        for _ in range(per_device):
            source = device if rng.random() < 0.9 else device.upper()
            events.append((t, source, rng.choice(variants)))
            t += rng.randint(int(w * 0.7), int(w * 2.0))

    # Chains: a tenth of the stream.
    target = len(events) + n // 10
    while len(events) < target:
        device, message = rng.choice(warm), rng.choice(CHAINS)
        t = T0 + rng.randrange(span)
        for _ in range(rng.randint(3, 40)):
            events.append((t, device, message))
            t += rng.randint(int(w * 0.55), int(w * 0.95))

    # Bursts: a quarter of the stream.
    target = len(events) + n // 4
    while len(events) < target:
        device, message = rng.choice(warm + cold), rng.choice(BURSTS)
        t = T0 + rng.randrange(span)
        for _ in range(rng.randint(2, 30)):
            events.append((t, device, message if rng.random() < 0.8 else message.upper()))
            t += rng.randint(0, w // 3)

    # One-offs: the rest.
    while len(events) < n:
        device = rng.choice(cold)
        kind = rng.randrange(3)
        if kind == 0:
            message = f'user {rng.randrange(50000)} signed in'
        elif kind == 1:
            message = f'job {rng.randrange(10**6)} finished in {rng.randrange(20, 9000)} ms'
        else:
            message = f'Firmware {rng.randrange(3)}.{rng.randrange(20)}.{rng.randrange(9)} installed'
        events.append((T0 + rng.randrange(span), device, message))
    del events[n:]

    # Arrival: timestamp plus jitter of less than one window.
    arrival = [ts + rng.randrange(w) for ts, _, _ in events]
    by_device = {}
    if replays:
        for i, (_, source, _) in enumerate(events):
            by_device.setdefault(source.casefold(), []).append(i)
    for _ in range(replays):
        device = rng.choice(hot + warm)
        start = T0 + rng.randrange(span)
        end = start + rng.randint(*outage_minutes) * 60_000
        upload = end + rng.randint(1, 20) * 60_000
        for i in by_device.get(device, ()):
            if start <= events[i][0] < end:
                arrival[i] = upload + (events[i][0] - start) // 1000
    order = sorted(range(len(events)), key=lambda i: (arrival[i], i))
    return [events[i] for i in order]
