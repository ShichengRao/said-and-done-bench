"""A small in-process event bus: handlers run in the publisher's thread."""

from __future__ import annotations

from collections import defaultdict


class EventBus:
    def __init__(self):
        self._handlers = defaultdict(list)

    def subscribe(self, topic: str, handler) -> None:
        self._handlers[topic].append(handler)

    def publish(self, topic: str, **payload) -> None:
        for handler in list(self._handlers[topic]):
            handler(**payload)
