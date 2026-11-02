"""What the docstring promises beyond the visible tests and the benchmark data.

The sample only has a little network jitter, so remembering just the last kept
event per key passes it; the day's backlogs are all under 80 minutes late, so
forgetting kept events after a couple of hours (the lookback suggested in
ISSUES/58.md) passes it too. Backlogs that arrive hours or days late need every
kept event within the window to count, however old. Also: keys that only
differ in where the source ends and the message starts, a window of 0, inputs
that are iterators, case folding beyond ASCII, no state carried between calls,
and random streams checked against the original implementation.
"""

import random
import signal

import pytest

from _reference import naive

from heron.dedupe import dedupe
from heron.events import Event

WINDOW = 1000
MINUTE = 60_000
HOUR = 60 * MINUTE
DAY = 24 * HOUR


def event(ts, message="Health check OK", source="edge-0001"):
    return Event(ts, source, message)


def as_tuples(events):
    return [(e.ts, e.source, e.message) for e in events]


@pytest.fixture
def time_limit():
    """Fails a test that runs past `seconds`: these inputs are big enough that only a fast dedupe gets through."""
    def on_alarm(signum, frame):
        raise AssertionError('dedupe took too long on this input')

    def set_limit(seconds):
        signal.signal(signal.SIGALRM, on_alarm)
        signal.alarm(seconds)

    yield set_limit
    signal.alarm(0)


def test_a_late_event_counts_against_every_kept_event_not_just_the_last():
    # 0 and 1500 are both kept; 300 arrives last, within the window of 0 but
    # not of 1500 (the most recently kept), so it's a duplicate.
    events = [event(0), event(1500), event(300)]
    assert dedupe(events, WINDOW) == [event(0), event(1500)]


def test_a_backlog_uploaded_after_reconnecting():
    # Heartbeats every 800 ms until the device goes offline at 10_000, live
    # again from 3_600_000, and the offline backlog uploaded after that.
    before = [event(ts) for ts in range(0, 10_000, 800)]
    live = [event(ts) for ts in range(3_600_000, 3_610_000, 800)]
    backlog = [event(ts) for ts in range(10_400, 3_600_000, 800)][:50]
    backlog.append(event(3_599_500))
    stream = before + live + backlog
    assert as_tuples(dedupe(stream, WINDOW)) == naive(as_tuples(stream), WINDOW)


def test_a_late_event_between_two_kept_events():
    events = [event(10_000), event(12_500), event(10_800), event(11_600)]
    # 10_800 is within the window of 10_000; 11_600 is more than a window from
    # 10_000 but within it of 12_500.
    assert dedupe(events, WINDOW) == [event(10_000), event(12_500)]


def test_late_events_hours_behind():
    hour = 3_600_000
    events = [event(5 * hour), event(5 * hour + 2000), event(2 * hour), event(2 * hour + 900),
              event(5 * hour + 1100), event(2 * hour + 1800)]
    # 5h+1100 is within the window of 5h+2000, though 2h was kept since.
    assert dedupe(events, WINDOW) == [
        event(5 * hour), event(5 * hour + 2000), event(2 * hour), event(2 * hour + 1800),
    ]


def test_a_backlog_a_day_late():
    # Heartbeats every 1.5 s until the device goes offline; it's back 30 hours
    # later, and its gateway re-sends the last few minutes before the outage
    # along with the backlog. Those repeat events that were kept a day ago.
    before = [event(ts) for ts in range(0, 10 * MINUTE, 1500)]
    live = [event(ts) for ts in range(30 * HOUR, 30 * HOUR + 10 * MINUTE, 1500)]
    resent = [event(ts + 200) for ts in range(5 * MINUTE, 10 * MINUTE, 1500)]
    kept = dedupe(before + live + resent, WINDOW)
    assert kept == before + live


def test_a_backlog_after_a_weekend():
    friday, monday = 4 * DAY + 17 * HOUR, 7 * DAY + 8 * HOUR
    events = [event(friday), event(friday + 5000), event(monday), event(monday + 5000),
              event(friday + 400), event(friday + 4200), event(friday + 2500)]
    # friday + 2500 is more than a window from both Friday events, so it's kept.
    assert dedupe(events, WINDOW) == [event(friday), event(friday + 5000), event(monday),
                                      event(monday + 5000), event(friday + 2500)]


@pytest.mark.parametrize('late_by', [3 * HOUR, 26 * HOUR, 9 * DAY], ids=['3h', '26h', '9d'])
def test_a_late_repeat_of_an_old_kept_event(late_by):
    # Other devices keep the clock moving while this one's repeat is in transit.
    others = [event(ts, "Link up", f"edge-{ts % 7:04d}") for ts in range(0, late_by, 10 * MINUTE)]
    events = [event(0)] + others + [event(late_by), event(300)]
    kept = dedupe(events, WINDOW)
    assert event(300) not in kept and kept[0] == event(0) and event(late_by) in kept


def test_a_long_history_then_a_late_event_near_its_start(time_limit):
    time_limit(30)
    history = [event(ts) for ts in range(0, 5000 * 1500, 1500)]
    late = [event(200), event(1500 * 2500 + 300), event(1500 * 4999 - 100)]
    assert dedupe(history + late, WINDOW) == history


def test_many_keys_then_their_repeats(time_limit):
    time_limit(30)
    first = [event(ts, f"job {ts} finished", f"node-{ts % 300:04d}") for ts in range(0, 60_000 * 50, 50)]
    repeats = [event(e.ts + 10, e.message.upper(), e.source.upper()) for e in first]
    assert dedupe(first + repeats, WINDOW) == first


@pytest.mark.parametrize('separator', [' ', ':', '|', '/', ',', '-', '_', '.', '@', '#', '='])
def test_where_the_source_ends_matters(separator):
    # One string per key, joined with a separator, can't tell these apart.
    a = event(0, f"7{separator}link up", "gw")
    b = event(10, "link up", f"gw{separator}7")
    assert dedupe([a, b], WINDOW) == [a, b]
    assert dedupe([b, a], WINDOW) == [b, a]


def test_each_call_starts_fresh():
    events = [event(0), event(5000, "Link up"), event(9000)]
    assert dedupe(events, WINDOW) == events
    again = [event(100), event(5100, "Link up"), event(8900)]
    assert dedupe(again, WINDOW) == again


def test_window_zero_drops_only_same_timestamp_repeats():
    events = [event(5), event(5, "health  CHECK ok"), event(6), event(4), event(5, source="EDGE-0001")]
    assert dedupe(events, 0) == [event(5), event(6), event(4)]


def test_window_zero_on_a_long_stream():
    rng = random.Random(3)
    stream = [event(rng.randrange(400), rng.choice("ab")) for _ in range(2000)]
    assert as_tuples(dedupe(stream, 0)) == naive(as_tuples(stream), 0)


def test_a_window_of_one():
    events = [event(10), event(11), event(12), event(9), event(8)]
    assert dedupe(events, 1) == [event(10), event(12), event(8)]


def test_a_huge_window_keeps_one_per_key():
    events = [event(ts * 997 % 50_000, msg) for ts in range(200) for msg in ("a", "b")]
    kept = dedupe(events, 10**12)
    assert as_tuples(kept) == as_tuples(events[:2])


def test_accepts_any_iterable():
    events = [event(0), event(400), event(1500), event(300)]
    expected = dedupe(list(events), WINDOW)
    assert dedupe(iter(events), WINDOW) == expected
    assert dedupe((e for e in events), WINDOW) == expected
    assert dedupe(tuple(events), WINDOW) == expected


def test_returns_a_list_and_leaves_the_input_alone():
    events = [event(0), event(400), event(1500)]
    copy = list(events)
    kept = dedupe(events, WINDOW)
    assert isinstance(kept, list) and events == copy


def test_case_folding_beyond_ascii():
    events = [event(0, "Straße sensor offline"), event(10, "STRASSE  SENSOR OFFLINE")]
    assert dedupe(events, WINDOW) == events[:1]


def test_whitespace_of_every_kind():
    events = [event(0, "disk full"), event(10, "\tdisk\n full  "), event(20, "disk full")]
    assert dedupe(events, WINDOW) == events[:1]


def test_identical_events():
    events = [event(7)] * 5
    assert dedupe(events, WINDOW) == [event(7)]


def test_random_streams_match_the_original():
    rng = random.Random(20261022)
    for case in range(400):
        window = rng.choice([0, 1, 3, 10, 50, 400])
        keys = [(rng.choice(["edge-1", "EDGE-1", "edge-2"]), rng.choice(["x", "X ", "y", " y"]))
                for _ in range(rng.randint(1, 4))]
        events = []
        for _ in range(rng.randint(0, 80)):
            source, message = rng.choice(keys)
            events.append(Event(rng.randrange(0, rng.choice([20, 200, 5000])), source, message))
        if rng.random() < 0.5:
            # Mostly in order, with a backlog arriving at the end.
            events.sort(key=lambda e: e.ts)
            cut = rng.randrange(len(events) + 1)
            backlog = events[cut // 2:cut]
            events = events[:cut // 2] + events[cut:] + backlog
        expected = naive(as_tuples(events), window)
        assert as_tuples(dedupe(events, window)) == expected, (case, window, as_tuples(events))


def test_random_streams_over_days_match_the_original():
    rng = random.Random(20261023)
    for case in range(150):
        window = rng.choice([0, 1000, 2000, 60_000])
        keys = [(rng.choice(["edge-1", "EDGE-1", "edge-2"]), rng.choice(["x", "X ", "y"]))
                for _ in range(rng.randint(1, 3))]
        events = []
        for _ in range(rng.randint(5, 25)):
            # Bursts of a few events around times spread over ten days.
            at = rng.randrange(10 * DAY)
            source, message = rng.choice(keys)
            events += [Event(at + rng.randrange(3 * max(window, 1)), source, message)
                       for _ in range(rng.randint(1, 6))]
        events.sort(key=lambda e: e.ts)
        # Some devices were offline: their events arrive at the end, hours to days late.
        late = [e for e in events if e.source == "edge-2"]
        events = [e for e in events if e.source != "edge-2"] + late
        if rng.random() < 0.3:
            rng.shuffle(events)
        expected = naive(as_tuples(events), window)
        assert as_tuples(dedupe(events, window)) == expected, (case, window, as_tuples(events))
