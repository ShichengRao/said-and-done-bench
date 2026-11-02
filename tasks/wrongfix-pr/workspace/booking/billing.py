"""Invoices for a stay, with optional parking."""

from decimal import Decimal

from booking.parking import ParkingPass
from booking.stays import Stay

NIGHTLY_RATE = Decimal("129.00")
PARKING_DAILY_RATE = Decimal("18.00")


def invoice_total(stay: Stay, parking: ParkingPass | None = None) -> Decimal:
    total = NIGHTLY_RATE * stay.nights
    if parking is not None:
        total += PARKING_DAILY_RATE * parking.days
    return total
