import pytest

from emsdest.recommend import NoEligibleDestination, recommend
from tests.helpers import make_feeds

NEAR = {'H-T1': 40, 'H-T2': 55, 'H-P1': 12, 'H-E1': 5, 'H-K1': 3}


def test_suspected_lvo_goes_to_the_nearest_thrombectomy_centre(tmp_path):
    destination = recommend('C-1', make_feeds(tmp_path, NEAR))
    assert destination['hospital'] == 'H-T1' and destination['tier'] == 'thrombectomy-capable centre'
    assert destination['drive_minutes'] == 40


def test_no_thrombectomy_centre_in_an_hour_falls_back_to_a_stroke_centre(tmp_path):
    destination = recommend('C-1', make_feeds(tmp_path, {**NEAR, 'H-T1': 65, 'H-T2': 70}))
    assert destination['hospital'] == 'H-P1' and destination['tier'] == 'stroke centre'


def test_a_low_lams_goes_to_the_nearest_stroke_centre(tmp_path):
    assert recommend('C-1', make_feeds(tmp_path, NEAR, lams=2))['hospital'] == 'H-P1'


def test_outside_the_window_is_not_a_suspected_lvo(tmp_path):
    feeds = make_feeds(tmp_path, NEAR, lkw='2025-12-30T09:00:00+00:00')
    assert recommend('C-1', feeds)['hospital'] == 'H-P1'


def test_a_hospital_that_is_not_a_stroke_centre_never_takes_a_stroke_alert(tmp_path):
    with pytest.raises(NoEligibleDestination) as raised:
        recommend('C-1', make_feeds(tmp_path, {**NEAR, 'H-T1': 65, 'H-T2': 70, 'H-P1': 31}))
    assert raised.value.reasons['H-E1'] == ['not a primary or thrombectomy stroke centre']
    assert raised.value.reasons['H-P1'] == ['31 min away, over 30 min']


def test_other_patients_go_to_the_nearest_adult_ed(tmp_path):
    destination = recommend('C-1', make_feeds(tmp_path, NEAR, stroke_alert=False, lams=None, lkw=None))
    assert destination['hospital'] == 'H-E1' and destination['tier'] == 'emergency department'
