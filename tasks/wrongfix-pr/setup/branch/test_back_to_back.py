from booking.rooms import room_is_free
from booking.stays import shared_nights
from tests.helpers import stay


def test_back_to_back_either_order():
    first, second = stay("ana", "2026-03-10", "2026-03-12"), stay("ben", "2026-03-12", "2026-03-15")
    assert shared_nights(first, second) == 0
    assert shared_nights(second, first) == 0


def test_room_is_free_after_a_checkout_the_same_day():
    assert room_is_free([stay("ana", "2026-04-01", "2026-04-05")], stay("ben", "2026-04-05", "2026-04-07"))
