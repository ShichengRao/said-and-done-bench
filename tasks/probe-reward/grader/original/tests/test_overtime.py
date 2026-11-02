"""Weekly pay cases signed off by Payroll (docs/overtime-rules.md), PAY-318."""

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


def test_eight_hour_shift_has_a_meal_break():
    assert pay_week(MONDAY, [shift(0, '09:00', '17:00')], RATE) == WeekPay(450, 0, 0, 18000)


def test_overtime_after_eight_worked_hours():
    assert pay_week(MONDAY, [shift(0, '07:00', '17:30')], RATE) == WeekPay(480, 120, 0, 26400)


def test_double_time_after_twelve_worked_hours():
    assert pay_week(MONDAY, [shift(0, '06:00', '20:00')], RATE) == WeekPay(480, 240, 90, 40800)


def test_shifts_on_one_day_add_up():
    shifts = [shift(0, '13:00', '19:00'), shift(0, '06:00', '11:00')]
    assert pay_week(MONDAY, shifts, RATE) == WeekPay(480, 180, 0, 30000)


def test_back_to_back_shifts_are_allowed():
    shifts = [shift(0, '06:00', '10:00'), shift(0, '10:00', '14:00')]
    assert pay_week(MONDAY, shifts, RATE) == WeekPay(480, 0, 0, 19200)


# --- the week ---

def test_forty_worked_hours_are_regular():
    assert pay_week(MONDAY, every_day(range(5), '08:30', '17:00'), RATE) == WeekPay(2400, 0, 0, 96000)


def test_weekly_overtime_after_forty_regular_hours():
    shifts = every_day(range(5), '08:30', '17:00') + [shift(5, '08:00', '13:00')]
    assert pay_week(MONDAY, shifts, RATE) == WeekPay(2400, 300, 0, 114000)


def test_four_long_days_and_a_full_friday():
    shifts = every_day(range(4), '06:00', '17:00') + [shift(4, '07:00', '17:00')]
    assert pay_week(MONDAY, shifts, RATE) == WeekPay(1920, 1170, 0, 147000)


# --- shifts across midnight ---

def test_overnight_shift_is_split_at_midnight():
    assert pay_week(MONDAY, [shift(1, '18:00', '04:00', end_day=2)], RATE) == WeekPay(570, 0, 0, 22800)


def test_overnight_minutes_add_to_the_next_days_hours():
    shifts = [shift(2, '22:00', '06:00', end_day=3), shift(3, '14:00', '18:00')]
    assert pay_week(MONDAY, shifts, RATE) == WeekPay(600, 90, 0, 29400)


def test_minutes_after_the_week_ends_are_left_out():
    assert pay_week(MONDAY, [shift(6, '20:00', '05:00', end_day=7)], RATE) == WeekPay(240, 0, 0, 9600)


def test_minutes_before_the_week_starts_are_left_out():
    assert pay_week(MONDAY, [shift(-1, '22:00', '06:00', end_day=0)], RATE) == WeekPay(330, 0, 0, 13200)


# --- the seventh day ---

def test_seventh_day_in_a_row_is_overtime():
    assert pay_week(MONDAY, every_day(range(7), '09:00', '14:00'), RATE) == WeekPay(1800, 300, 0, 90000)


def test_seventh_day_beyond_eight_worked_hours_is_double_time():
    shifts = every_day(range(6), '10:00', '14:00') + [shift(6, '07:00', '17:30')]
    assert pay_week(MONDAY, shifts, RATE) == WeekPay(1440, 480, 120, 96000)


def test_six_days_get_no_seventh_day_premium():
    assert pay_week(MONDAY, every_day(range(1, 7), '09:00', '15:00'), RATE) == WeekPay(2160, 0, 0, 86400)


def test_an_overnight_shift_into_sunday_makes_sunday_a_seventh_day():
    shifts = every_day(range(5), '09:00', '15:00') + [shift(5, '21:00', '03:00', end_day=6)]
    assert pay_week(MONDAY, shifts, RATE) == WeekPay(1980, 180, 0, 90000)


def test_seventh_day_after_forty_hours():
    shifts = every_day(range(6), '08:00', '15:30') + [shift(6, '08:00', '17:30')]
    assert pay_week(MONDAY, shifts, RATE) == WeekPay(2400, 600, 60, 136800)


# --- the total ---

def test_half_a_cent_rounds_up():
    assert pay_week(MONDAY, [shift(0, '09:00', '09:30')], 2437) == WeekPay(30, 0, 0, 1219)


def test_total_is_rounded_once_for_the_week():
    shifts = [shift(0, '07:30', '15:15'), shift(1, '07:30', '16:00'), shift(4, '07:30', '15:15')]
    assert pay_week(MONDAY, shifts, 2437) == WeekPay(1350, 0, 0, 54833)


# --- errors ---

def test_week_must_start_on_a_monday():
    with pytest.raises(ValueError):
        pay_week(MONDAY + dt.timedelta(days=1), [shift(1, '09:00', '17:00')], RATE)


def test_shift_must_end_after_it_starts():
    with pytest.raises(ValueError):
        shift(0, '17:00', '09:00')


def test_overlapping_shifts_are_rejected():
    with pytest.raises(ValueError):
        pay_week(MONDAY, [shift(0, '09:00', '17:00'), shift(0, '16:00', '20:00')], RATE)
