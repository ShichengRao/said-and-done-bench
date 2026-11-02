from skylift.checks import zone_problems
from tests.helpers import make_feeds


def problems(feeds, zone_id, request='R-1'):
    zone = next(zone for zone in feeds.zones if zone.id == zone_id)
    return zone_problems(zone, feeds.request(request), feeds)


def test_a_zone_inside_every_limit_has_no_problems(tmp_path):
    assert problems(make_feeds(tmp_path), 'T-1') == []


def test_gusts_over_the_limit(tmp_path):
    feeds = make_feeds(tmp_path, wind={'T-1': (8.0, 13.5)})
    assert problems(feeds, 'T-1') == ['gusts 13.5 m/s, over the 13 m/s limit']


def test_gusts_at_the_limit_are_fine(tmp_path):
    assert problems(make_feeds(tmp_path, wind={'T-1': (10.0, 13.0)}), 'T-1') == []


def test_sustained_wind_over_the_limit(tmp_path):
    assert problems(make_feeds(tmp_path, wind={'T-1': (10.5, 12.0)}), 'T-1') == ['wind 10.5 m/s, over the 10 m/s limit']


def test_a_leg_beyond_the_aircraft_range(tmp_path):
    assert problems(make_feeds(tmp_path), 'T-3') == ['leg 20.0 km, over the 17.0 km limit']


def test_a_zone_at_another_clinic(tmp_path):
    assert problems(make_feeds(tmp_path), 'O-1') == ['serves otherton, not testville']


def test_a_closure_covering_the_arrival(tmp_path):
    feeds = make_feeds(tmp_path, notices=[{
        'id': 'N-1', 'zone': 'T-1', 'kind': 'closure', 'starts': '2026-01-10T09:30:00+00:00',
        'ends': '2026-01-10T12:00:00+00:00', 'text': 'fete'}])
    assert problems(feeds, 'T-1') == ['closed until 12:00 (N-1: fete)']


def test_a_closure_that_ends_before_the_arrival(tmp_path):
    feeds = make_feeds(tmp_path, notices=[{
        'id': 'N-1', 'zone': 'T-1', 'kind': 'closure', 'starts': '2026-01-10T08:00:00+00:00',
        'ends': '2026-01-10T10:00:00+00:00', 'text': 'fete'}])
    assert problems(feeds, 'T-1') == []  # 5 km at 72 km/h: arrives 10:04.


def test_a_temporary_obstacle_too_close(tmp_path):
    feeds = make_feeds(tmp_path, notices=[{
        'id': 'N-2', 'zone': 'T-2', 'kind': 'obstacle', 'starts': '2026-01-10T07:00:00+00:00',
        'ends': '2026-01-10T18:00:00+00:00', 'text': 'crane', 'clearance_m': 11}])
    assert problems(feeds, 'T-2') == ['obstacle 11 m from touchdown, under 15 m (N-2: crane)']
