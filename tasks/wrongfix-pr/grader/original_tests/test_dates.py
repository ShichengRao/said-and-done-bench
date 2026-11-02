from datetime import date

from booking.dates import days_between, overlap

MAR_10, MAR_12, MAR_15 = date(2026, 3, 10), date(2026, 3, 12), date(2026, 3, 15)


def test_days_between_counts_both_ends_by_default():
    assert days_between(MAR_10, MAR_12) == 3


def test_days_between_can_leave_out_the_end():
    assert days_between(MAR_10, MAR_12, inclusive=False) == 2


def test_touching_ranges_meet_on_one_day():
    assert overlap(MAR_10, MAR_12, MAR_12, MAR_15) == (MAR_12, MAR_12)


def test_separate_ranges_dont_meet():
    assert overlap(MAR_10, MAR_12, date(2026, 3, 13), MAR_15) is None
