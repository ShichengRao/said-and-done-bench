"""Room availability."""

from booking.stays import Stay, shared_nights


def room_is_free(existing: list[Stay], new: Stay) -> bool:
    """Whether new can go in its room alongside the stays already booked there."""
    return all(shared_nights(stay, new) == 0 for stay in existing if stay.room == new.room)


def occupancy(stays: list[Stay], room: str) -> int:
    """Nights the room is booked across stays, counting shared nights once."""
    booked = [stay for stay in stays if stay.room == room]
    total = sum(stay.nights for stay in booked)
    for i, a in enumerate(booked):
        for b in booked[i + 1:]:
            total -= shared_nights(a, b)
    return total
