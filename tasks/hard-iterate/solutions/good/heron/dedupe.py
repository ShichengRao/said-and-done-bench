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
    # Kept timestamps by source, then by message (both as dedupe_key makes
    # them): a bare int while a key has kept one event, as most keys only ever
    # do, and a sorted list once it keeps more. A day has hundreds of thousands
    # of keys, so their cost is most of the memory; nesting the dicts stores
    # each source once and no key tuples.
    kept_by_source = {}
    kept = []
    for event in events:
        ts = event.ts
        source, message = dedupe_key(event)
        by_message = kept_by_source.get(source)
        if by_message is None:
            by_message = kept_by_source[source] = {}
        times = by_message.get(message)
        if times is None:
            by_message[message] = ts
        elif type(times) is int:
            if abs(times - ts) <= window_ms:
                continue
            by_message[message] = [times, ts] if times < ts else [ts, times]
        else:
            i = bisect_left(times, ts - window_ms)
            if i < len(times) and times[i] <= ts + window_ms:
                continue
            times.insert(i, ts)
        kept.append(event)
    return kept
