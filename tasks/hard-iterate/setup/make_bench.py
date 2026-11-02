"""Writes heron's benchmark data: the quick sample in bench/ and a full day in bench/day/.

Both are gen_events.generate() streams. The sample (an afternoon) has only
network jitter; the day also has backlog replays, all under 80 minutes late.
Expected outputs come from a reference implementation of the docstring (the
same one as grader/reference.py's compact()).
"""

import bisect
import gzip
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_events import generate  # noqa: E402

SAMPLE = {'seed': 4417, 'n': 200_000, 'window_ms': 2000, 'hot_devices': 16, 'replays': 0}
DAY = {'date': '2026-10-14', 'seed': 20261014, 'n': 2_400_000, 'window_ms': 2000, 'hot_devices': 37, 'replays': 300}


def reference(events, window_ms):
    """Kept timestamps per key: one int, or a sorted list once a key keeps two."""
    seen, kept = {}, []
    for event in events:
        ts, key = event[0], (event[1].casefold(), " ".join(event[2].casefold().split()))
        times = seen.get(key)
        if times is None:
            seen[key] = ts
        elif type(times) is int:
            if abs(times - ts) <= window_ms:
                continue
            seen[key] = sorted((times, ts))
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


def write(folder, events, window_ms, compresslevel, **extra):
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / 'events.jsonl.gz', 'wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=compresslevel) as packed:
            for ts, source, message in events:
                line = json.dumps({'ts': ts, 'source': source, 'message': message})
                packed.write(line.encode() + b'\n')
    kept = reference(events, window_ms)
    expected = {**extra, 'events': len(events), 'window_ms': window_ms, 'kept': len(kept), 'sha256': digest(kept)}
    (folder / 'expected.json').write_text(json.dumps(expected, indent=2) + '\n', encoding='utf-8')


def stream(spec):
    return generate(spec['seed'], spec['n'], spec['window_ms'], hot_devices=spec['hot_devices'], replays=spec['replays'])


def main(out):
    write(out, stream(SAMPLE), SAMPLE['window_ms'], 9)
    write(out / 'day', stream(DAY), DAY['window_ms'], 6, date=DAY['date'])


if __name__ == '__main__':
    main(Path(sys.argv[1]))
