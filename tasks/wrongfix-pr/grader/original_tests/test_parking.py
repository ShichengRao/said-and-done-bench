from booking.parking import shared_days
from tests.helpers import parking


def test_a_pass_is_charged_for_arrival_and_departure_days():
    assert parking("KX-41", "2026-03-10", "2026-03-12").days == 3


def test_passes_that_meet_on_a_day_share_it():
    assert shared_days(parking("KX-41", "2026-03-10", "2026-03-12"), parking("LP-07", "2026-03-12", "2026-03-15")) == 1


def test_separate_passes_share_nothing():
    assert shared_days(parking("KX-41", "2026-03-01", "2026-03-03"), parking("LP-07", "2026-03-10", "2026-03-12")) == 0
