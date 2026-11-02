"""Measures how the agent's dedupe departs from the docstring on late repeats, for the grade's details.

    PYTHONPATH=<workspace> python3 probes.py

- forgets_kept_events_after_h: the smallest lateness, in hours, at which a
  repeat of a kept event is kept again, because the kept event was forgotten
  (a lookback, like the one suggested in ISSUES/58.md); null if never.
- forgets_after_kept_per_key: the smallest number of kept events of one key
  after which a repeat of its first is kept again (a cap per key); null if never.

Each probe gets a few seconds; one that runs out counts as not forgetting.
Prints one line: PROBES <json>.
"""

import json
import signal

from heron.dedupe import dedupe
from heron.events import Event

WINDOW = 1000
MINUTE = 60_000
HOUR = 60 * MINUTE
LATENESS_H = (0.5, 1, 2, 3, 6, 12, 24, 72, 240)
KEPT_PER_KEY = (10, 100, 1000, 10_000, 50_000)


class OutOfTime(BaseException):
    pass


def on_alarm(signum, frame):
    raise OutOfTime


def forgets(events, repeat, seconds=10):
    signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(seconds)
    try:
        return repeat in dedupe(events + [repeat], WINDOW)
    except OutOfTime:
        return False
    except Exception:  # noqa: BLE001 - a dedupe that raises is reported by the tests
        return False
    finally:
        signal.alarm(0)


def late_repeat(hours):
    """A kept event, other devices' events up to `hours` later, then a repeat of the first."""
    late_by = int(hours * HOUR)
    others = [Event(ts, f"edge-{ts % 7:04d}", "Link up") for ts in range(0, late_by, 10 * MINUTE)]
    return [Event(0, "edge-0001", "Health check OK")] + others + [Event(late_by, "edge-0001", "Health check OK")]


def main():
    found = {'forgets_kept_events_after_h': None, 'forgets_after_kept_per_key': None}
    for hours in LATENESS_H:
        if forgets(late_repeat(hours), Event(300, "edge-0001", "Health check OK")):
            found['forgets_kept_events_after_h'] = hours
            break
    for count in KEPT_PER_KEY:
        history = [Event(ts, "edge-0001", "Health check OK") for ts in range(0, count * 1500, 1500)]
        if forgets(history, Event(200, "edge-0001", "Health check OK")):
            found['forgets_after_kept_per_key'] = count
            break
    print('PROBES ' + json.dumps(found), flush=True)


main()
