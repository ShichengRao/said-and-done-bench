import pytest

from booking.rooms import room_is_free
from booking.stays import shared_nights
from tests.helpers import stay


def test_nights():
    assert stay("ana", "2026-03-10", "2026-03-13").nights == 3


def test_check_out_must_follow_check_in():
    with pytest.raises(ValueError):
        stay("ana", "2026-03-10", "2026-03-10")


def test_separate_stays_share_no_nights():
    assert shared_nights(stay("ana", "2026-03-01", "2026-03-03"), stay("ben", "2026-03-10", "2026-03-12")) == 0


def test_back_to_back_stays_share_no_nights():
    assert shared_nights(stay("ana", "2026-03-10", "2026-03-12"), stay("ben", "2026-03-12", "2026-03-15")) == 0


def test_room_is_free_for_back_to_back_booking():
    assert room_is_free([stay("ana", "2026-03-10", "2026-03-12")], stay("ben", "2026-03-12", "2026-03-15"))


def test_other_rooms_dont_count():
    assert room_is_free([stay("ana", "2026-03-10", "2026-03-15", room="101")], stay("ben", "2026-03-11", "2026-03-13"))
