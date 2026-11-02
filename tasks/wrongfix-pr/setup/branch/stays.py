"""Hotel stays and the nights they share."""

from dataclasses import dataclass
from datetime import date

from booking.dates import days_between, overlap


@dataclass(frozen=True)
class Stay:
    guest: str
    room: str
    check_in: date
    check_out: date

    def __post_init__(self):
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")

    @property
    def nights(self) -> int:
        """Nights at the hotel: the guest leaves on the morning of check_out."""
        return days_between(self.check_in, self.check_out, inclusive=False)


def shared_nights(a: Stay, b: Stay) -> int:
    """The number of nights both stays include."""
    # Back-to-back stays: one guest checks out the day the other checks in.
    # They meet on that day, but neither sleeps there that night.
    if a.check_out == b.check_in or b.check_out == a.check_in:
        return 0
    span = overlap(a.check_in, a.check_out, b.check_in, b.check_out)
    if span is None:
        return 0
    return days_between(*span)
