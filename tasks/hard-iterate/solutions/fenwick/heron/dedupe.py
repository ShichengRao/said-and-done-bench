"""Dropping repeated device events before they're stored."""

from bisect import bisect_left, bisect_right


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
    # Per-key Fenwick trees over each key's distinct timestamps: counting the
    # kept events in [ts - window_ms, ts + window_ms] is two prefix sums.
    events = list(events)
    keys = [dedupe_key(event) for event in events]
    by_key = {}
    for key, event in zip(keys, events):
        by_key.setdefault(key, []).append(event.ts)
    key_ts = {key: sorted(set(times)) for key, times in by_key.items()}
    trees = {key: [0] * (len(times) + 1) for key, times in key_ts.items()}
    kept = []
    for event, key in zip(events, keys):
        times, tree = key_ts[key], trees[key]
        ts = event.ts
        count = 0
        i = bisect_right(times, ts + window_ms)
        while i:
            count += tree[i]
            i -= i & -i
        i = bisect_left(times, ts - window_ms)
        while i:
            count -= tree[i]
            i -= i & -i
        if count:
            continue
        i = bisect_left(times, ts) + 1
        while i < len(tree):
            tree[i] += 1
            i += i & -i
        kept.append(event)
    return kept
