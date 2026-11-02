"""Parking passes, charged per calendar day.

A guest parks on the day they arrive and the day they leave, so a pass from
Mar 10 to Mar 12 is charged for 3 days, and two passes that meet on a day
both use that day.
"""

from dataclasses import dataclass
from datetime import date

from booking.dates import days_between, overlap


@dataclass(frozen=True)
class ParkingPass:
    plate: str
    start: date
    end: date

    @property
    def days(self) -> int:
        return days_between(self.start, self.end)


def shared_days(a: ParkingPass, b: ParkingPass) -> int:
    """Days both passes use the same space."""
    span = overlap(a.start, a.end, b.start, b.end)
    return 0 if span is None else days_between(*span)
