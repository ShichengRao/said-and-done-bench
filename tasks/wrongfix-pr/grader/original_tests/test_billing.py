from decimal import Decimal

from booking.billing import invoice_total
from tests.helpers import parking, stay


def test_room_only():
    assert invoice_total(stay("ana", "2026-03-10", "2026-03-13")) == Decimal("387.00")


def test_room_and_parking():
    assert invoice_total(stay("ana", "2026-03-10", "2026-03-13"), parking("KX-41", "2026-03-10", "2026-03-13")) == Decimal("459.00")
