"""The standard capture analysis: lost messages and queueing delay.

The gateway doesn't count what it loses, so loss is read from the capture:
every producer numbers its messages 0, 1, 2, ..., and a number missing from
the capture below the producer's highest captured one is a lost message.
"""

from dataclasses import dataclass

from gateway import capture


@dataclass
class Stats:
    messages: int  # Messages the capture accounts for: captured plus lost.
    lost: int
    p99_wait_ms: float
    max_wait_ms: float

    def summary(self):
        share = 100 * self.lost / self.messages if self.messages else 0.0
        return (
            f'lost {self.lost:,} of {self.messages:,} messages ({share:.3f}%); '
            f'p99 wait {self.p99_wait_ms:,.1f} ms, max wait {self.max_wait_ms:,.1f} ms'
        )


def analyze(directory):
    """Stats for the capture in `directory`, or None if it holds no records."""
    seen = {}  # producer -> (count, highest seq)
    waits = []
    for _, start_ms, records in capture.read(directory):
        for producer, seq, arrival, _ in records:
            count, highest = seen.get(producer, (0, -1))
            seen[producer] = (count + 1, max(highest, seq))
            waits.append(start_ms - arrival)
    if not waits:
        return None
    messages = sum(highest + 1 for _, highest in seen.values())
    captured = sum(count for count, _ in seen.values())
    waits.sort()
    return Stats(messages, messages - captured, waits[min(len(waits) - 1, int(len(waits) * 0.99))], waits[-1])
