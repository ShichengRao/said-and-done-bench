from datetime import date

from booking.parking import ParkingPass
from booking.stays import Stay


def stay(guest, check_in, check_out, room="204"):
    return Stay(guest, room, date.fromisoformat(check_in), date.fromisoformat(check_out))


def parking(plate, start, end):
    return ParkingPass(plate, date.fromisoformat(start), date.fromisoformat(end))
