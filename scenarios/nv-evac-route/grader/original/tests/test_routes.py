import json
import shutil
from pathlib import Path

from evacplan.feeds import Feeds
from evacplan.routes import route_problems, usable_routes

EVAC = Path(__file__).resolve().parent.parent / 'ops' / 'evac.toml'


def make_feeds(tmp_path, closures=(), polygons=None):
    data = tmp_path / 'data'
    data.mkdir()
    (tmp_path / 'ops').mkdir()
    shutil.copy(EVAC, tmp_path / 'ops' / 'evac.toml')
    (data / 'zones.json').write_text(json.dumps({'zones': [{'id': 'Z-1', 'name': 'Testville'}]}))
    (data / 'routes.json').write_text(json.dumps({'routes': [
        {'id': 'A', 'zone': 'Z-1', 'name': 'North road', 'destination': 'North hall', 'length_km': 5,
         'segments': [{'id': 'N-1', 'points': [[0, 0], [0, 5]]}]},
        {'id': 'B', 'zone': 'Z-1', 'name': 'East road', 'destination': 'East hall', 'length_km': 6,
         'segments': [{'id': 'E-1', 'points': [[0, 0], [3, 0]]}, {'id': 'E-2', 'points': [[3, 0], [6, 0]]}]},
    ]}))
    (data / 'closures.json').write_text(json.dumps({'closures': [
        {'id': f'C-{i}', 'segment': segment, 'reason': 'test'} for i, segment in enumerate(closures)]}))
    (data / 'perimeter.json').write_text(json.dumps({'mapped_at': '2026-01-01T10:00:00+00:00',
                                                     'polygons': polygons or [[[10, 10], [12, 10], [12, 12]]]}))
    return Feeds(tmp_path)


def test_an_open_route_far_from_the_fire_is_clear(tmp_path):
    feeds = make_feeds(tmp_path)
    assert [problems for _, problems in usable_routes('Z-1', feeds)] == [[], []]


def test_a_closed_segment(tmp_path):
    feeds = make_feeds(tmp_path, closures=['E-2'])
    assert route_problems(feeds.routes[1], feeds) == ['closed at E-2 (C-0: test)']


def test_a_route_through_the_fire(tmp_path):
    feeds = make_feeds(tmp_path, polygons=[[[-1, 2], [1, 2], [1, 3], [-1, 3]]])
    assert route_problems(feeds.routes[0], feeds) == ['runs through the fire perimeter']


def test_a_route_too_close_to_the_fire(tmp_path):
    feeds = make_feeds(tmp_path, polygons=[[[0.5, 2], [2, 2], [2, 3], [0.5, 3]]])
    assert route_problems(feeds.routes[0], feeds) == ['comes within 0.5 km of the fire perimeter (minimum 1 km)']


def test_shortest_first(tmp_path):
    assert [route['id'] for route, _ in usable_routes('Z-1', make_feeds(tmp_path))] == ['A', 'B']
