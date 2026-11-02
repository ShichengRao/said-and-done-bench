"""Dropping repeated device events before they're stored."""

from bisect import bisect_left


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
    # Kept timestamps by "source:message" (as dedupe_key makes them): a bare
    # int while a key has kept one event, and a sorted list once it keeps more.
    # One string per key is far smaller than a tuple of two.
    seen = {}
    kept = []
    for event in events:
        ts = event.ts
        source, message = dedupe_key(event)
        key = source + ":" + message
        times = seen.get(key)
        if times is None:
            seen[key] = ts
        elif type(times) is int:
            if abs(times - ts) <= window_ms:
                continue
            seen[key] = [times, ts] if times < ts else [ts, times]
        else:
            i = bisect_left(times, ts - window_ms)
            if i < len(times) and times[i] <= ts + window_ms:
                continue
            times.insert(i, ts)
        kept.append(event)
    return kept
