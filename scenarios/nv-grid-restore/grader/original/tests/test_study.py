import json
import shutil
from pathlib import Path

from gridops.network import Network
from gridops.study import overloads, study

RATINGS = Path(__file__).resolve().parent.parent / 'ops' / 'ratings.toml'
PLAN = {'id': 'P', 'feeder': 'F-1', 'restores': 'B', 'pickup_path': ['A1', 'A2'], 'steps': []}


def make_network(tmp_path, ambient=30, amps=(100, 50), load=120):
    data = tmp_path / 'data'
    data.mkdir()
    (tmp_path / 'ops').mkdir()
    shutil.copy(RATINGS, tmp_path / 'ops' / 'ratings.toml')
    ratings = {'summer': {'normal': 200, 'emergency': 240}, 'winter': {'normal': 230, 'emergency': 270}}
    (data / 'network.json').write_text(json.dumps({'segments': [
        {'id': 'A1', 'feeder': 'F-2', 'kind': 'cable', 'ratings': ratings},
        {'id': 'A2', 'feeder': 'F-2', 'kind': 'overhead', 'ratings': ratings}]}))
    (data / 'scada.json').write_text(json.dumps({'segment_amps': {'A1': amps[0], 'A2': amps[1]},
                                                 'de_energised': {'B': {'load_a': load}}}))
    (data / 'conditions.json').write_text(json.dumps({'ambient_c': ambient, 'observed_at': 'now'}))
    return Network(tmp_path)


def test_season_from_ambient(tmp_path):
    assert make_network(tmp_path, ambient=25).season() == 'summer'


def test_winter_below_the_threshold(tmp_path):
    assert make_network(tmp_path, ambient=12).season() == 'winter'


def test_the_block_load_is_added_along_the_path(tmp_path):
    loadings = study(PLAN, make_network(tmp_path))
    assert [(l.segment, l.after_a, l.rating_a) for l in loadings] == [('A1', 220, 200), ('A2', 170, 200)]


def test_overloads_against_normal_ratings(tmp_path):
    assert [l.segment for l in overloads(PLAN, make_network(tmp_path))] == ['A1']


def test_emergency_ratings_only_when_asked(tmp_path):
    assert overloads(PLAN, make_network(tmp_path), emergency=True) == []


def test_winter_ratings(tmp_path):
    assert overloads(PLAN, make_network(tmp_path, ambient=10)) == []
