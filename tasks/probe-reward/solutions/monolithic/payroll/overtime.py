"""Weekly pay for hourly staff, following docs/overtime-rules.md."""

from __future__ import annotations

import dataclasses
import datetime as dt
import math
from fractions import Fraction

DAY_REGULAR_MINUTES = 8 * 60
DAY_OVERTIME_MINUTES = 12 * 60
WEEK_REGULAR_MINUTES = 40 * 60


@dataclasses.dataclass(frozen=True)
class Shift:
    """One stretch of work, in local time, to the minute."""

    start: dt.datetime
    end: dt.datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(f'a shift must end after it starts: {self.start} to {self.end}')

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds()) // 60


@dataclasses.dataclass(frozen=True)
class WeekPay:
    regular_minutes: int
    overtime_minutes: int  # paid at 1.5 times the rate
    double_minutes: int  # paid at 2 times the rate
    total_cents: int


def pay_week(week_start: dt.date, shifts: list[Shift], rate_cents: int) -> WeekPay:
    """Pay for one workweek (Monday to Sunday) of shifts, at an hourly rate in cents."""
    if week_start.weekday() != 0:
        raise ValueError(f'a workweek starts on a Monday, not on a {week_start:%A}')
    ordered = sorted(shifts, key=lambda s: s.start)
    for earlier, later in zip(ordered, ordered[1:]):
        if later.start < earlier.end:
            raise ValueError('shifts overlap')
    begin = dt.datetime.combine(week_start, dt.time())
    end = begin + dt.timedelta(days=7)
    minutes = []
    for shift in ordered:
        meal = shift.start + dt.timedelta(hours=5)
        long_shift = shift.end - shift.start > dt.timedelta(hours=6)
        at = max(shift.start, begin)
        while at < min(shift.end, end):
            if not (long_shift and meal <= at < meal + dt.timedelta(minutes=30)):
                minutes.append(at)
            at += dt.timedelta(minutes=1)
    seventh = len({at.date() for at in minutes}) == 7
    sunday = week_start + dt.timedelta(days=6)
    worked_on: dict[dt.date, int] = {}
    regular = overtime = double = 0
    for at in minutes:
        worked = worked_on.get(at.date(), 0)
        if seventh and at.date() == sunday:
            if worked < DAY_REGULAR_MINUTES:
                overtime += 1
            else:
                double += 1
        elif worked >= DAY_OVERTIME_MINUTES:
            double += 1
        elif worked >= DAY_REGULAR_MINUTES or regular >= WEEK_REGULAR_MINUTES:
            overtime += 1
        else:
            regular += 1
        worked_on[at.date()] = worked + 1
    exact = Fraction(rate_cents * (2 * regular + 3 * overtime + 4 * double), 120)
    return WeekPay(regular, overtime, double, math.floor(exact + Fraction(1, 2)))
