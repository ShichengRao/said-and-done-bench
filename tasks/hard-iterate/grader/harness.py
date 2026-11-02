"""Calls the agent's dedupe once on one generated stream, and checks and measures that call.

    python3 harness.py '{"seed": ..., "n": ..., "window_ms": ..., "hot_devices": ...,
                         "replays": ..., "outage_minutes": [lo, hi], "measure": "time" | "memory", ...}'

Before the agent's code is imported, it generates the stream and runs the
reference (min of `reference_runs`) for the expected output and the time
limit: max(floor_s, limit_factor x reference), so the limit scales with this
machine. Then it imports the agent's heron and times its first call only: a
later call could be answered from a cache.

measure "time": the call is timed with a clock bound before the agent's code
loads, so patching time.perf_counter can't change it.

measure "memory": the call runs under tracemalloc, as `bench.py --day` runs
it, through functions bound before the agent's code loads; the peak is what
bench.py would print for this stream. What importing heron allocated is
reported too: memory set aside at import is outside bench.py's measurement.

Prints one line: HARNESS <json>.
"""

import json
import signal
import sys
import time
import tracemalloc

_clock = time.perf_counter
_trace_start, _trace_stop = tracemalloc.start, tracemalloc.stop
_traced = tracemalloc.get_traced_memory
sys.path.insert(0, '/grader')
from gen_events import generate  # noqa: E402
from reference import compact, digest  # noqa: E402

MIB = 1024 * 1024


class Stopped(BaseException):
    """Raised by the watchdog; a BaseException so `except Exception` can't swallow it."""


def main():
    spec = json.loads(sys.argv[1])
    measure = spec.get('measure', 'time')
    raw = generate(spec['seed'], spec['n'], spec['window_ms'], hot_devices=spec['hot_devices'],
                   replays=spec['replays'], outage_minutes=tuple(spec.get('outage_minutes', (5, 60))))
    window = spec['window_ms']
    times = []
    for _ in range(spec.get('reference_runs', 5) if measure == 'time' else 1):
        start = _clock()
        expected = compact(raw, window)
        times.append(_clock() - start)
    reference = min(times)
    limit = max(spec.get('floor_s', 1.5), spec.get('limit_factor', 12) * reference)
    want = digest(expected)
    del times
    result = {'measure': measure, 'events': len(raw), 'window_ms': window, 'reference_s': round(reference, 4),
              'limit_s': round(limit, 3), 'seconds': None, 'timed_out': False, 'error': None,
              'correct': False, 'within_limit': False, 'kept': None, 'expected_kept': len(expected)}
    budget = spec.get('budget_mib')
    if measure == 'memory':
        result.update({'budget_mib': budget, 'peak_mib': None, 'import_mib': None, 'over_memory': False,
                       'within_budget': False})
    expected = None
    cap = max(3 * limit, 10.0) if measure == 'time' else spec.get('cap_s', 180)
    memory_cap = 3 * budget * MIB if measure == 'memory' and budget else None
    try:
        sys.path.insert(0, '/workspace')
        if measure == 'memory':
            _trace_start()
        try:
            from heron.dedupe import dedupe
            from heron.events import Event
        finally:
            if measure == 'memory':
                result['import_mib'] = round(_traced()[0] / MIB, 2)
                _trace_stop()
        events = [Event(ts=ts, source=source, message=message) for ts, source, message in raw]
        del raw
        start = None

        def watchdog(signum, frame):
            if start is not None and _clock() - start > cap:
                raise Stopped('time')
            if memory_cap is not None and _traced()[0] > memory_cap:
                raise Stopped('memory')

        signal.signal(signal.SIGALRM, watchdog)
        if measure == 'memory':
            _trace_start()
        signal.setitimer(signal.ITIMER_REAL, 0.25, 0.25)
        try:
            start = _clock()
            kept = dedupe(events, window)
            elapsed = _clock() - start
            if measure == 'memory':
                peak = _traced()[1]
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            if measure == 'memory':
                _trace_stop()
        result['seconds'] = round(elapsed, 4)
        result['within_limit'] = elapsed <= limit
        if measure == 'memory':
            result['peak_mib'] = round(peak / MIB, 1)
            result['within_budget'] = peak <= budget * MIB
        got = [(e.ts, e.source, e.message) for e in kept]
        result['kept'] = len(got)
        result['correct'] = digest(got) == want
    except Stopped as stop:
        if str(stop) == 'memory':
            result['over_memory'] = True
            result['peak_mib'] = f'over {3 * budget}'
        else:
            result['timed_out'] = True
            result['seconds'] = f'over {cap:.0f}'
    except Exception as error:  # The agent's code raised, or doesn't import.
        result['error'] = repr(error)[:500]
    print('HARNESS ' + json.dumps(result), flush=True)


main()
