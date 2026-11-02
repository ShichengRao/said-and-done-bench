"""Device events as the ingest pipeline sees them."""

from typing import NamedTuple


class Event(NamedTuple):
    ts: int  # When the device recorded the event, in milliseconds since the epoch.
    source: str  # The device's id, such as "edge-0417".
    message: str
