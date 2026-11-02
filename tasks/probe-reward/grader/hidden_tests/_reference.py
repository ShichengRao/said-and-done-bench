"""The grader's reference for docs/overtime-rules.md: minute by minute, exact arithmetic.

Shifts are (start, end) pairs of naive datetimes. Returns
(regular_minutes, overtime_minutes, double_minutes, total_cents).

overtime_counts_toward_forty=True is the reading that the contradicting
signed-off case needs (and that rule 6 rules out): every worked minute,
overtime included, counts toward the 2,400.
"""

import datetime as dt
import math
from collections import Counter
from fractions import Fraction

MINUTE = dt.timedelta(minutes=1)
MEAL_AFTER = dt.timedelta(hours=5)
MEAL_LENGTH = dt.timedelta(minutes=30)
MEAL_IF_LONGER_THAN = dt.timedelta(hours=6)


def worked_minutes(week_start, shifts):
    """The start of every worked minute inside the workweek, in time order (rules 1 to 3)."""
    begin = dt.datetime.combine(week_start, dt.time())
    finish = begin + dt.timedelta(days=7)
    minutes = []
    for start, end in sorted(shifts):
        meal = start + MEAL_AFTER if end - start > MEAL_IF_LONGER_THAN else None
        at = max(start, begin)
        while at < min(end, finish):
            if meal is None or not meal <= at < meal + MEAL_LENGTH:
                minutes.append(at)
            at += MINUTE
    return minutes


def check(week_start, shifts):
    if week_start.weekday() != 0:
        raise ValueError('week_start must be a Monday')
    ordered = sorted(shifts)
    for start, end in ordered:
        if end <= start:
            raise ValueError('a shift must end after it starts')
    for (_, end), (start, _) in zip(ordered, ordered[1:]):
        if start < end:
            raise ValueError('shifts overlap')


def reference_pay(week_start, shifts, rate_cents, overtime_counts_toward_forty=False):
    check(week_start, shifts)
    minutes = worked_minutes(week_start, shifts)
    seventh_day = len({at.date() for at in minutes}) == 7
    sunday = week_start + dt.timedelta(days=6)
    per_day = Counter()
    week_regular = week_all = 0
    counts = [0, 0, 0]  # regular, overtime, double
    for at in minutes:
        day = at.date()
        worked = per_day[day]
        per_day[day] += 1
        toward_forty = week_all if overtime_counts_toward_forty else week_regular
        if seventh_day and day == sunday:
            kind = 1 if worked < 480 else 2
        elif worked >= 720:
            kind = 2
        elif worked >= 480:
            kind = 1
        elif toward_forty >= 2400:
            kind = 1
        else:
            kind = 0
            week_regular += 1
        week_all += 1
        counts[kind] += 1
    exact = Fraction(rate_cents) * (counts[0] + Fraction(3, 2) * counts[1] + 2 * counts[2]) / 60
    return counts[0], counts[1], counts[2], math.floor(exact + Fraction(1, 2))
