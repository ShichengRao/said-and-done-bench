"""What a feed holds once it's read."""

from __future__ import annotations

import dataclasses
import datetime as dt


@dataclasses.dataclass(frozen=True)
class Reading:
    at: dt.datetime  # aware, in UTC
    level_m: float  # metres above chart datum


@dataclasses.dataclass
class Feed:
    """One feed file's rows for one station."""

    station: str
    readings: list[Reading]
    flagged: list[dt.datetime] = dataclasses.field(default_factory=list)  # instants of S and B rows
    missing: list[dt.datetime] = dataclasses.field(default_factory=list)  # instants of M rows
