"""Weekly pay: daily and weekly overtime."""

import datetime as dt

import pytest

from payroll import Shift, WeekPay, pay_week

MONDAY = dt.date(2026, 3, 2)
RATE = 2400  # $24.00 an hour


def at(day, clock):
    """`day` counts from MONDAY (0 = Monday, 6 = Sunday, 7 = the next Monday)."""
    hours, minutes = map(int, clock.split(':'))
    return dt.datetime.combine(MONDAY + dt.timedelta(days=day), dt.time(hours, minutes))


def shift(day, start, end, end_day=None):
    return Shift(at(day, start), at(day if end_day is None else end_day, end))


def every_day(days, start, end):
    return [shift(day, start, end) for day in days]


# --- one day ---

def test_six_hours_are_regular():
    assert pay_week(MONDAY, [shift(0, '09:00', '15:00')], RATE) == WeekPay(360, 0, 0, 14400)


def test_shifts_on_one_day_add_up():
    shifts = [shift(0, '13:00', '19:00'), shift(0, '06:00', '11:00')]
    assert pay_week(MONDAY, shifts, RATE) == WeekPay(480, 180, 0, 30000)


def test_back_to_back_shifts_are_allowed():
    shifts = [shift(0, '06:00', '10:00'), shift(0, '10:00', '14:00')]
    assert pay_week(MONDAY, shifts, RATE) == WeekPay(480, 0, 0, 19200)


# --- errors ---

def test_week_must_start_on_a_monday():
    with pytest.raises(ValueError):
        pay_week(MONDAY + dt.timedelta(days=1), [shift(1, '09:00', '17:00')], RATE)


def test_shift_must_end_after_it_starts():
    with pytest.raises(ValueError):
        shift(0, '17:00', '09:00')
