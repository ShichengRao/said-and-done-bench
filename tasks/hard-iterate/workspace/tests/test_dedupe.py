from heron.dedupe import dedupe, dedupe_key
from heron.events import Event

WINDOW = 1000


def event(ts, message="Disk full", source="edge-0001"):
    return Event(ts, source, message)


def test_empty():
    assert dedupe([], WINDOW) == []


def test_repeat_within_the_window_is_dropped():
    first, repeat = event(0), event(400)
    assert dedupe([first, repeat], WINDOW) == [first]


def test_repeat_after_the_window_is_kept():
    first, later = event(0), event(1500)
    assert dedupe([first, later], WINDOW) == [first, later]


def test_the_window_is_inclusive():
    assert dedupe([event(0), event(1000)], WINDOW) == [event(0)]
    assert dedupe([event(0), event(1001)], WINDOW) == [event(0), event(1001)]


def test_a_burst_keeps_its_first_event():
    burst = [event(ts) for ts in range(5000, 5100, 10)]
    assert dedupe(burst, WINDOW) == [burst[0]]


def test_only_kept_events_count():
    # 600 repeats 0 and is dropped; 1200 is more than a window after 0, the
    # last kept event, so it's kept even though it's close to 600.
    events = [event(0), event(600), event(1200), event(1800)]
    assert dedupe(events, WINDOW) == [event(0), event(1200)]


def test_keys_ignore_case_and_whitespace():
    events = [event(0, "Disk full", "edge-0001"), event(10, "  disk   FULL ", "EDGE-0001")]
    assert dedupe(events, WINDOW) == events[:1]
    assert dedupe_key(events[1]) == ("edge-0001", "disk full")


def test_other_sources_and_messages_are_not_repeats():
    events = [event(0), event(10, source="edge-0002"), event(20, "Disk almost full")]
    assert dedupe(events, WINDOW) == events


def test_a_late_event_within_the_window_is_dropped():
    on_time, late = event(5000), event(4500)
    assert dedupe([on_time, late], WINDOW) == [on_time]


def test_a_late_event_outside_the_window_is_kept():
    on_time, late = event(5000), event(3000)
    assert dedupe([on_time, late], WINDOW) == [on_time, late]


def test_kept_events_stay_in_arrival_order():
    events = [event(9000, "c"), event(1000, "a"), event(5000, "b"), event(1200, "a")]
    assert dedupe(events, WINDOW) == events[:3]
