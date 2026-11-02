import json

import pytest

from emsdest.data import Feeds
from emsdest.recommend import NoEligibleDestination, recommend
from tests.helpers import make_feeds

NEAR = {'H-T1': 40, 'H-T2': 55, 'H-P1': 12, 'H-E1': 5, 'H-K1': 3}


def with_board(tmp_path, minutes, board, **case):
    make_feeds(tmp_path, minutes, **case)
    (tmp_path / 'data' / 'status_board.json').write_text(json.dumps({'status': [
        {'hospital': hospital, 'ed': ed, 'stroke': stroke, 'reason': 'test'} for hospital, (ed, stroke) in board.items()]}))
    return Feeds(tmp_path)


def test_stroke_diversion_skips_to_the_next_thrombectomy_centre(tmp_path):
    feeds = with_board(tmp_path, NEAR, {'H-T1': ('open', 'diversion')})
    assert recommend('C-1', feeds)['hospital'] == 'H-T2'


def test_ed_diversion_rules_a_hospital_out_for_everyone(tmp_path):
    feeds = with_board(tmp_path, NEAR, {'H-E1': ('diversion', 'n/a')}, stroke_alert=False, lams=None, lkw=None)
    assert recommend('C-1', feeds)['hospital'] == 'H-P1'


def test_stroke_diversion_does_not_matter_for_other_patients(tmp_path):
    feeds = with_board(tmp_path, NEAR, {'H-E1': ('open', 'diversion')}, stroke_alert=False, lams=None, lkw=None)
    assert recommend('C-1', feeds)['hospital'] == 'H-E1'


def test_every_stroke_centre_on_diversion(tmp_path):
    feeds = with_board(tmp_path, NEAR, {'H-T1': ('open', 'diversion'), 'H-T2': ('open', 'diversion'),
                                        'H-P1': ('diversion', 'diversion')})
    with pytest.raises(NoEligibleDestination):
        recommend('C-1', feeds)
