"""The gateway: a FIFO buffer drained by a pool of workers, with the egress capture on the hot path.

An arriving message goes to an idle drain worker if there is one, and
otherwise waits in the buffer (`buffer_slots` messages). If the buffer is
full, the message is lost: the gateway keeps no count of that (it's how the
2026-10-14 loss went unnoticed); lost messages show up only as gaps in the
producers' sequence numbers in the capture (see gateway/analysis.py).

A free worker takes up to `drain_batch` messages from the head of the buffer
and forwards them, which takes
    drain_overhead_ms + (sum of sizes in KiB) * drain_ms_per_kib
plus capturing the batch, which takes
    (compressed KiB the capture wrote for it) * capture_ms_per_kib
before the worker is free again.
"""

import heapq
from collections import deque


class Gateway:
    def __init__(self, capture, *, buffer_slots, drain_workers, drain_batch, drain_overhead_ms,
                 drain_ms_per_kib, capture_ms_per_kib, progress=None):
        if buffer_slots < 0 or drain_workers < 1 or drain_batch < 1:
            raise ValueError('need buffer_slots >= 0, drain_workers >= 1 and drain_batch >= 1')
        self.capture = capture
        self.slots = buffer_slots
        self.workers = drain_workers
        self.batch = drain_batch
        self.overhead_ms = drain_overhead_ms
        self.ms_per_kib = drain_ms_per_kib
        self.capture_ms_per_kib = capture_ms_per_kib
        self.progress = progress  # Called as progress(t_ms, queued, forwarded) once a simulated minute.
        self.buffer = deque()
        self.forwarded = 0

    def run(self, messages):
        """Push messages, (producer, seq, arrival_ms, size_kib, body) in arrival order, through the gateway."""
        busy = []  # Heap of (free at, worker).
        idle = list(range(self.workers))
        next_report = 60_000.0
        for message in messages:
            arrival = message[2]
            self._drain(busy, idle, until=arrival)
            while self.progress and arrival >= next_report:
                self.progress(next_report, len(self.buffer), self.forwarded)
                next_report += 60_000.0
            if idle:
                self.buffer.append(message)
                self._start(busy, min(idle), arrival)
                idle.remove(min(idle))
            elif len(self.buffer) < self.slots:
                self.buffer.append(message)
            # Otherwise the buffer is full and the message is lost.
        self._drain(busy, idle, until=float('inf'))

    def _drain(self, busy, idle, until):
        while busy and busy[0][0] <= until:
            free_at, worker = heapq.heappop(busy)
            if self.buffer:
                self._start(busy, worker, free_at)
            else:
                idle.append(worker)

    def _start(self, busy, worker, now):
        batch = [self.buffer.popleft() for _ in range(min(self.batch, len(self.buffer)))]
        captured = self.capture.append(worker, now, batch)
        took = (
            self.overhead_ms
            + sum(message[3] for message in batch) * self.ms_per_kib
            + captured / 1024 * self.capture_ms_per_kib
        )
        self.forwarded += len(batch)
        heapq.heappush(busy, (now + took, worker))
