"""Reference implementations of heron's dedupe docstring, on (ts, source, message) tuples."""

import bisect
import hashlib


def key(source, message):
    return (source.casefold(), " ".join(message.casefold().split()))


def naive(events, window_ms):
    """The original implementation: compare with every kept event."""
    kept = []
    for event in events:
        k = key(event[1], event[2])
        if not any(key(o[1], o[2]) == k and abs(o[0] - event[0]) <= window_ms for o in kept):
            kept.append(event)
    return kept


def bucketed(events, window_ms):
    """Kept events with the same key are more than window_ms apart, so each
    bucket of window_ms + 1 milliseconds holds at most one of them per key."""
    width, kept_at, kept = window_ms + 1, {}, []
    for event in events:
        ts = event[0]
        k, bucket = key(event[1], event[2]), ts // width
        if any(abs(kept_at.get((k, b), ts + width + window_ms) - ts) <= window_ms
               for b in (bucket - 1, bucket, bucket + 1)):
            continue
        kept_at[(k, bucket)] = ts
        kept.append(event)
    return kept


def compact(events, window_ms):
    """Kept timestamps per key: one int, or a sorted list once a key keeps two.
    The fastest of the three; the grader times it to scale its limits."""
    seen, kept = {}, []
    for event in events:
        ts, k = event[0], key(event[1], event[2])
        times = seen.get(k)
        if times is None:
            seen[k] = ts
        elif type(times) is int:
            if abs(times - ts) <= window_ms:
                continue
            seen[k] = sorted((times, ts))
        else:
            i = bisect.bisect_left(times, ts - window_ms)
            if i < len(times) and times[i] <= ts + window_ms:
                continue
            times.insert(i, ts)
        kept.append(event)
    return kept


def digest(events):
    sha = hashlib.sha256()
    for ts, source, message in events:
        sha.update(f"{ts}\t{source}\t{message}\n".encode())
    return sha.hexdigest()
