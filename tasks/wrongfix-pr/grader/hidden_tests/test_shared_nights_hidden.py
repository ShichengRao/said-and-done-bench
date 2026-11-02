"""Overlaps the issue didn't mention, and the parking rules a fix mustn't break."""

from datetime import date
from decimal import Decimal

import pytest

from booking.billing import invoice_total
from booking.dates import days_between
from booking.parking import ParkingPass, shared_days
from booking.rooms import occupancy, room_is_free
from booking.stays import Stay, shared_nights


def stay(guest, check_in, check_out, room="204"):
    return Stay(guest, room, date.fromisoformat(check_in), date.fromisoformat(check_out))


def parking(plate, start, end):
    return ParkingPass(plate, date.fromisoformat(start), date.fromisoformat(end))


@pytest.mark.parametrize(
    ("a", "b", "nights"),
    [
        (("2026-03-10", "2026-03-15"), ("2026-03-12", "2026-03-20"), 3),  # partial overlap
        (("2026-03-10", "2026-03-13"), ("2026-03-12", "2026-03-20"), 1),  # one shared night
        (("2026-03-10", "2026-03-12"), ("2026-03-10", "2026-03-12"), 2),  # the same stay
        (("2026-03-01", "2026-03-31"), ("2026-03-10", "2026-03-12"), 2),  # one inside the other
        (("2025-12-30", "2026-01-02"), ("2026-01-01", "2026-01-05"), 1),  # across new year
        (("2026-03-10", "2026-03-12"), ("2026-03-12", "2026-03-15"), 0),  # back to back
        (("2026-03-01", "2026-03-03"), ("2026-03-10", "2026-03-12"), 0),  # apart
    ],
)
def test_shared_nights(a, b, nights):
    first, second = stay("ana", *a), stay("ben", *b)
    assert shared_nights(first, second) == nights
    assert shared_nights(second, first) == nights


def test_room_is_taken_by_a_partial_overlap():
    assert not room_is_free([stay("ana", "2026-03-10", "2026-03-15")], stay("ben", "2026-03-14", "2026-03-16"))


def test_room_is_free_between_two_stays():
    existing = [stay("ana", "2026-03-01", "2026-03-05"), stay("cy", "2026-03-08", "2026-03-10")]
    assert room_is_free(existing, stay("ben", "2026-03-05", "2026-03-08"))


def test_occupancy_counts_shared_nights_once():
    stays = [stay("ana", "2026-03-10", "2026-03-15"), stay("ben", "2026-03-13", "2026-03-18")]
    assert occupancy(stays, "204") == 8


def test_parking_still_charges_both_ends():
    assert parking("KX-41", "2026-03-10", "2026-03-12").days == 3
    assert days_between(date(2026, 3, 10), date(2026, 3, 12)) == 3


def test_parking_passes_still_share_the_day_they_meet():
    assert shared_days(parking("KX-41", "2026-03-10", "2026-03-12"), parking("LP-07", "2026-03-12", "2026-03-15")) == 1
    assert shared_days(parking("KX-41", "2026-03-10", "2026-03-15"), parking("LP-07", "2026-03-12", "2026-03-20")) == 4


def test_invoices_are_unchanged():
    assert invoice_total(stay("ana", "2026-03-10", "2026-03-13"), parking("KX-41", "2026-03-10", "2026-03-13")) == Decimal("459.00")
