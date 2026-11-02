"""Weekly pay for hourly staff, following docs/overtime-rules.md."""

from __future__ import annotations

import dataclasses
import datetime as dt
import math
from collections import Counter
from fractions import Fraction

DAY_REGULAR_MINUTES = 8 * 60
DAY_OVERTIME_MINUTES = 12 * 60
WEEK_REGULAR_MINUTES = 40 * 60
MINUTE = dt.timedelta(minutes=1)
MEAL_IF_LONGER_THAN = dt.timedelta(hours=6)
MEAL_AFTER = dt.timedelta(hours=5)
MEAL_LENGTH = dt.timedelta(minutes=30)
REGULAR, OVERTIME, DOUBLE = 0, 1, 2
MULTIPLIERS = (Fraction(1), Fraction(3, 2), Fraction(2))


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


def _check(week_start: dt.date, shifts: list[Shift]) -> list[Shift]:
    if week_start.weekday() != 0:
        raise ValueError(f'a workweek starts on a Monday, not on a {week_start:%A}')
    ordered = sorted(shifts, key=lambda s: s.start)
    for earlier, later in zip(ordered, ordered[1:]):
        if later.start < earlier.end:
            raise ValueError(f'shifts overlap: {earlier} and {later}')
    return ordered


def _meal_break(shift: Shift) -> tuple[dt.datetime, dt.datetime] | None:
    """The unpaid break in a shift longer than 6 hours (rule 3)."""
    if shift.end - shift.start <= MEAL_IF_LONGER_THAN:
        return None
    start = shift.start + MEAL_AFTER
    return start, start + MEAL_LENGTH


def _minutes_in_week(week_start: dt.date, shifts: list[Shift]) -> list[dt.datetime]:
    """The start of every worked minute inside the workweek, in time order (rules 1 to 3)."""
    begin = dt.datetime.combine(week_start, dt.time())
    end = begin + dt.timedelta(days=7)
    minutes = []
    for shift in shifts:
        meal = _meal_break(shift)
        at = max(shift.start, begin)
        while at < min(shift.end, end):
            if meal is None or not meal[0] <= at < meal[1]:
                minutes.append(at)
            at += MINUTE
    return minutes


def _daily_kind(worked_today: int, seventh_day: bool) -> int:
    """The rate rules 4 and 5 give a day's next worked minute."""
    if seventh_day:
        return OVERTIME if worked_today < DAY_REGULAR_MINUTES else DOUBLE
    if worked_today >= DAY_OVERTIME_MINUTES:
        return DOUBLE
    return OVERTIME if worked_today >= DAY_REGULAR_MINUTES else REGULAR


def _classify(week_start: dt.date, minutes: list[dt.datetime]) -> list[int]:
    """How many minutes are paid at each rate (rules 4 to 7)."""
    worked_all_week = len({at.date() for at in minutes}) == 7
    sunday = week_start + dt.timedelta(days=6)
    per_day: Counter[dt.date] = Counter()
    counts = [0, 0, 0]
    for at in minutes:
        kind = _daily_kind(per_day[at.date()], worked_all_week and at.date() == sunday)
        if kind == REGULAR and sum(counts) >= WEEK_REGULAR_MINUTES:
            kind = OVERTIME
        per_day[at.date()] += 1
        counts[kind] += 1
    return counts


def pay_week(week_start: dt.date, shifts: list[Shift], rate_cents: int) -> WeekPay:
    """Pay for one workweek (Monday to Sunday) of shifts, at an hourly rate in cents."""
    ordered = _check(week_start, shifts)
    counts = _classify(week_start, _minutes_in_week(week_start, ordered))
    exact = sum(Fraction(rate_cents) * n * m / 60 for n, m in zip(counts, MULTIPLIERS))
    return WeekPay(*counts, total_cents=math.floor(exact + Fraction(1, 2)))
