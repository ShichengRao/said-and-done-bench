import pytest

from gateway.engine import Gateway

SETTINGS = dict(drain_workers=1, drain_batch=4, drain_overhead_ms=10.0, drain_ms_per_kib=0.0, capture_ms_per_kib=1.0)


class FakeCapture:
    """Records batches; every append 'writes' a fixed number of bytes."""

    def __init__(self, bytes_per_append=0):
        self.batches = []
        self.bytes_per_append = bytes_per_append

    def append(self, worker, start_ms, batch):
        self.batches.append((worker, start_ms, [message[1] for message in batch]))
        return self.bytes_per_append


def messages(*arrivals):
    return [('svc', seq, float(t), 1.0, b'') for seq, t in enumerate(arrivals)]


def run(arrivals, slots, capture=None, **overrides):
    capture = capture or FakeCapture()
    Gateway(capture, buffer_slots=slots, **{**SETTINGS, **overrides}).run(messages(*arrivals))
    return capture.batches


def test_idle_gateway_forwards_each_message_at_once():
    assert run([0, 50, 100], slots=0) == [(0, 0.0, [0]), (0, 50.0, [1]), (0, 100.0, [2])]


def test_waiting_messages_go_in_batches():
    assert run([0, 1, 2, 3, 4, 5], slots=10) == [(0, 0.0, [0]), (0, 10.0, [1, 2, 3, 4]), (0, 20.0, [5])]


def test_full_buffer_loses_the_newest_messages():
    # Message 0 goes straight to the worker; 1 and 2 fill the buffer; 3 and 4 are lost.
    assert run([0, 1, 2, 3, 4], slots=2) == [(0, 0.0, [0]), (0, 10.0, [1, 2])]


def test_capture_bytes_cost_drain_time():
    batches = run([0, 1], slots=5, capture=FakeCapture(bytes_per_append=10 * 1024))
    assert batches == [(0, 0.0, [0]), (0, 20.0, [1])]  # 10 ms overhead + 10 KiB * 1 ms/KiB


def test_workers_share_the_load():
    assert run([0, 0, 0], slots=0, drain_workers=3) == [(0, 0.0, [0]), (1, 0.0, [1]), (2, 0.0, [2])]


def test_bad_settings():
    with pytest.raises(ValueError):
        Gateway(FakeCapture(), buffer_slots=-1, **SETTINGS)
