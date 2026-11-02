"""Dropping repeated device events before they're stored."""

import heapq

LOOKBACK_MS = 2 * 60 * 60 * 1000


def dedupe_key(event):
    """Two events repeat each other when their keys match: the same source,
    ignoring case, and the same message, ignoring case and whitespace
    differences (runs of spaces or tabs, leading and trailing whitespace)."""
    return (event.source.casefold(), " ".join(event.message.casefold().split()))


def dedupe(events, window_ms):
    """Drop repeated events, keeping the first of each burst.

    `events` is an iterable of Event in arrival order. An event is a duplicate
    when an event with the same key that was already kept has a timestamp
    within `window_ms` milliseconds of its own (before or after it, inclusive).
    Duplicates are dropped; every other event is kept.

    Arrival order isn't timestamp order. Devices buffer events while they're
    offline and upload the backlog after they reconnect, so an event can arrive
    hours or days after events with later timestamps (a device that was off
    over a weekend). Only kept events count, so which events are kept depends
    on the order they arrive in.

    `window_ms` is an int >= 0; with 0, only events with the same key and the
    same timestamp are duplicates. Returns a list of the kept events in arrival
    order.
    """
    # As in the Go ingester (see ISSUES/58.md): kept events more than
    # LOOKBACK_MS behind the newest timestamp seen are forgotten, which keeps
    # memory flat. Backlogs are never that late in practice.
    width = window_ms + 1
    by_key = {}  # key -> {bucket: timestamp of the kept event there}
    expiry = []  # heap of (timestamp, key, bucket) for every kept event still remembered
    newest = None
    kept = []
    for event in events:
        ts = event.ts
        if newest is None or ts > newest:
            newest = ts
            while expiry and expiry[0][0] < newest - LOOKBACK_MS:
                _, old_key, old_bucket = heapq.heappop(expiry)
                buckets = by_key[old_key]
                del buckets[old_bucket]
                if not buckets:
                    del by_key[old_key]
        key = dedupe_key(event)
        bucket = ts // width
        buckets = by_key.get(key)
        if buckets is None:
            buckets = by_key[key] = {}
        if any(other is not None and abs(other - ts) <= window_ms
               for other in (buckets.get(bucket - 1), buckets.get(bucket), buckets.get(bucket + 1))):
            continue
        buckets[bucket] = ts
        heapq.heappush(expiry, (ts, key, bucket))
        kept.append(event)
    return kept
