"""Hidden checks for PAY-318: the rules on other weeks, rates, and shapes of week.

Every expected value comes from _reference.py, which follows
docs/overtime-rules.md minute by minute with exact arithmetic.
"""

import datetime as dt
import random

import pytest

from _reference import reference_pay
from payroll import Shift, pay_week


def result(week_start, shifts, rate):
    pay = pay_week(week_start, [Shift(start, end) for start, end in shifts], rate)
    return pay.regular_minutes, pay.overtime_minutes, pay.double_minutes, pay.total_cents


def week_of(monday):
    def at(day, clock):
        hours, minutes = map(int, clock.split(':'))
        return dt.datetime.combine(monday + dt.timedelta(days=day), dt.time(hours, minutes))
    return at


MAR = dt.date(2026, 3, 2)  # the visible tests' week
NOV = dt.date(2026, 11, 16)
FEB = dt.date(2027, 2, 22)  # Sunday is Feb 28; the next Monday is Mar 1
LEAP = dt.date(2028, 2, 28)  # Tuesday is Feb 29
m, n, f, p = week_of(MAR), week_of(NOV), week_of(FEB), week_of(LEAP)

CASES = {
    # docs/overtime-rules.md's worked example, which one signed-off case contradicts.
    'worked_example': (MAR, [(m(d, '06:00'), m(d, '17:00')) for d in range(4)] + [(m(4, '07:00'), m(4, '17:00'))], 2400),
    'worked_example_other_rate': (MAR, [(m(d, '06:00'), m(d, '17:00')) for d in range(4)]
                                  + [(m(4, '07:00'), m(4, '17:00'))], 3150),
    'long_days_then_regular_minutes': (NOV, [(n(d, '05:30'), n(d, '18:00')) for d in range(3)]
                                       + [(n(3, '08:00'), n(3, '18:30')), (n(4, '08:00'), n(4, '16:00'))], 2675),
    'meal_break_across_midnight': (NOV, [(n(2, '19:30'), n(3, '02:30'))], 2290),
    'meal_break_in_the_next_week': (NOV, [(n(6, '21:00'), n(7, '04:00'))], 2290),
    'nights_across_midnight': (NOV, [(n(d, '21:00'), n(d + 1, '07:30')) for d in range(4)], 3125),
    'night_then_day_shift': (NOV, [(n(0, '20:00'), n(1, '02:00')), (n(1, '08:00'), n(1, '15:00'))], 2890),
    'long_days_to_double_time': (NOV, [(n(d, '05:00'), n(d, '19:45')) for d in range(3)], 2215),
    'seven_days_with_long_sunday': (FEB, [(f(d, '06:00'), f(d, '12:00')) for d in range(6)]
                                    + [(f(6, '04:00'), f(6, '19:00'))], 3399),
    'seven_days_and_weekly_overtime': (FEB, [(f(d, '07:00'), f(d, '16:00')) for d in range(7)], 2777),
    'saturday_night_into_sunday': (FEB, [(f(d, '08:00'), f(d, '14:00')) for d in range(5)]
                                   + [(f(5, '22:30'), f(6, '01:15'))], 1985),
    'sunday_night_into_next_week': (LEAP, [(p(d, '09:00'), p(d, '17:00')) for d in range(5)]
                                    + [(p(6, '18:00'), p(7, '06:00'))], 2604),
    'previous_week_into_monday': (LEAP, [(p(-1, '19:00'), p(0, '09:00')), (p(1, '09:00'), p(1, '23:00'))], 2049),
    'leap_day_overnight': (LEAP, [(p(1, '16:00'), p(2, '04:00')), (p(2, '10:00'), p(2, '18:00'))], 2333),
    'many_short_shifts': (NOV, [(n(d, f'{h:02d}:00'), n(d, f'{h:02d}:50')) for d in range(7) for h in (6, 9, 13)],
                          1777),
    'unsorted_input': (NOV, [(n(4, '09:00'), n(4, '19:00')), (n(0, '09:00'), n(0, '19:00')),
                             (n(2, '09:00'), n(2, '19:00')), (n(1, '09:00'), n(1, '19:00')),
                             (n(3, '09:00'), n(3, '19:00'))], 2500),
    'half_cents_round_up': (FEB, [(f(0, '08:00'), f(0, '08:30')), (f(2, '08:00'), f(2, '09:30'))], 1913),
    'one_minute': (NOV, [(n(2, '12:00'), n(2, '12:01'))], 2999),
}


@pytest.mark.parametrize('name', sorted(CASES))
def test_case(name):
    week_start, shifts, rate = CASES[name]
    assert result(week_start, shifts, rate) == reference_pay(week_start, shifts, rate)


def random_week(rng):
    monday = dt.date(2026, 1, 5) + dt.timedelta(weeks=rng.randrange(150))
    begin = dt.datetime.combine(monday, dt.time())
    shifts = []
    if rng.random() < 0.5:
        # One shift on most days: long weeks, seventh days, weekly overtime.
        for day in range(-1, 8):
            if rng.random() < (0.9 if 0 <= day < 7 else 0.3):
                start = begin + dt.timedelta(days=day, minutes=rng.randrange(0, 24 * 60, 5))
                shifts.append((start, start + dt.timedelta(minutes=rng.randrange(30, 15 * 60, 5))))
    else:
        for _ in range(rng.randrange(1, 14)):
            start = begin + dt.timedelta(minutes=rng.randrange(-12 * 60, 8 * 24 * 60))
            shifts.append((start, start + dt.timedelta(minutes=rng.randrange(1, 17 * 60))))
    kept = []
    for start, end in sorted(shifts):
        if not kept or start >= kept[-1][1]:
            kept.append((start, end))
    rng.shuffle(kept)
    return monday, kept, rng.randrange(1500, 4600)


@pytest.mark.parametrize('seed', range(20))
def test_random_weeks_match_the_rules(seed):
    rng = random.Random(f'pay-318:{seed}')
    for _ in range(25):
        week_start, shifts, rate = random_week(rng)
        assert result(week_start, shifts, rate) == reference_pay(week_start, shifts, rate), (week_start, shifts, rate)


def test_overlap_anywhere_is_rejected():
    with pytest.raises(ValueError):
        result(NOV, [(n(0, '09:00'), n(0, '12:00')), (n(3, '08:00'), n(3, '10:00')), (n(3, '09:59'), n(3, '11:00'))],
               2400)


def test_overlap_with_a_shift_inside_another_is_rejected():
    with pytest.raises(ValueError):
        result(NOV, [(n(1, '06:00'), n(1, '18:00')), (n(1, '09:00'), n(1, '10:00'))], 2400)


def test_week_starting_on_a_sunday_is_rejected():
    with pytest.raises(ValueError):
        result(NOV - dt.timedelta(days=1), [(n(0, '09:00'), n(0, '12:00'))], 2400)
