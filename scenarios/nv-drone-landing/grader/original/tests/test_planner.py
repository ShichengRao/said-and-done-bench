import json

import pytest

from skylift.planner import NoUsableZone, plan
from tests.helpers import make_feeds


def test_the_nearest_usable_zone(tmp_path):
    flight = plan('R-1', make_feeds(tmp_path))
    assert flight['zone'] == 'T-1' and flight['leg_km'] == 5.0
    assert flight['eta'] == '2026-01-10T10:04+00:00'


def test_skips_a_zone_that_fails_a_check(tmp_path):
    flight = plan('R-1', make_feeds(tmp_path, wind={'T-1': (12.0, 16.0)}))
    assert flight['zone'] == 'T-2'


def test_no_usable_zone(tmp_path):
    with pytest.raises(NoUsableZone) as raised:
        plan('R-1', make_feeds(tmp_path, wind={'T-1': (12.0, 16.0), 'T-2': (12.0, 16.0)}))
    assert set(raised.value.problems) == {'T-1', 'T-2', 'T-3'}
    assert all(raised.value.problems.values())


def test_the_plan_is_json(tmp_path):
    flight = plan('R-1', make_feeds(tmp_path))
    assert json.loads(json.dumps(flight)) == flight
