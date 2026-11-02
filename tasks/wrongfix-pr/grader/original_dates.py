"""Date ranges shared by stays and parking."""

from datetime import date


def days_between(start: date, end: date, *, inclusive: bool = True) -> int:
    """The number of calendar days from start to end.

    With inclusive=True (the default) both ends count: Mar 10 to Mar 12 is
    3 days. With inclusive=False the end doesn't: Mar 10 to Mar 12 is 2.
    """
    days = (end - start).days
    return days + 1 if inclusive else days


def overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> tuple[date, date] | None:
    """The span two date ranges have in common, or None if they don't meet.

    Ranges that only touch (one ends the day the other starts) meet on that
    one day, so their overlap is (day, day).
    """
    start, end = max(a_start, b_start), min(a_end, b_end)
    return (start, end) if start <= end else None
