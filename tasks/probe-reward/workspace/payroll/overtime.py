"""Weekly pay for hourly staff, following docs/overtime-rules.md."""

from __future__ import annotations

import dataclasses
import datetime as dt

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
    worked_on: dict[dt.date, int] = {}
    regular = overtime = double = week_minutes = 0
    total_cents = 0
    for shift in sorted(shifts, key=lambda s: s.start):
        day = shift.start.date()
        before = (regular, overtime, double)
        for _ in range(shift.minutes):
            worked = worked_on.get(day, 0)
            if worked >= DAY_OVERTIME_MINUTES:
                double += 1
            elif worked >= DAY_REGULAR_MINUTES or week_minutes >= WEEK_REGULAR_MINUTES:
                overtime += 1
            else:
                regular += 1
            worked_on[day] = worked + 1
            week_minutes += 1
        added = [now - then for now, then in zip((regular, overtime, double), before)]
        shift_pay = rate_cents * (added[0] + 1.5 * added[1] + 2 * added[2]) / 60
        total_cents += round(shift_pay)
    return WeekPay(regular, overtime, double, total_cents)
