"""Dropping repeated device events before they're stored."""


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
    # Kept events with the same key are more than window_ms apart, so a bucket
    # window_ms + 1 milliseconds wide holds at most one of them per key, and any
    # kept event within window_ms of ts is in ts's bucket or one next to it.
    width = window_ms + 1
    kept_at = {}  # (key, bucket) -> timestamp of the kept event there
    kept = []
    for event in events:
        key = dedupe_key(event)
        ts = event.ts
        bucket = ts // width
        for neighbour in (bucket - 1, bucket, bucket + 1):
            other = kept_at.get((key, neighbour))
            if other is not None and abs(other - ts) <= window_ms:
                break
        else:
            kept_at[(key, bucket)] = ts
            kept.append(event)
    return kept
