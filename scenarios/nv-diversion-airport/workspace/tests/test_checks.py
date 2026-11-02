from divert.checks import assess, options, required_on_landing
from tests.helpers import make_feeds

ILS = ('ILS 18', 200, 550)


def check(tmp_path, **kwargs):
    feeds = make_feeds(tmp_path, **kwargs)
    return {option.icao: option for option in options(feeds.flight('T100'), feeds)}


def test_fuel_required_on_landing(tmp_path):
    feeds = make_feeds(tmp_path, {'XAAA': (2500, [ILS])}, {'XAAA': (1000, 5000)})
    assert required_on_landing(feeds) == 1200


def test_an_airport_that_meets_everything(tmp_path):
    found = check(tmp_path, airports={'XAAA': (2500, [ILS])}, weather={'XAAA': (1000, 5000)})
    assert found['XAAA'].problems == [] and found['XAAA'].approach == 'ILS 18'
    assert found['XAAA'].fuel_at_arrival_kg == 3800


def test_weather_below_minima(tmp_path):
    found = check(tmp_path, airports={'XAAA': (2500, [ILS])}, weather={'XAAA': (150, 2000)})
    assert found['XAAA'].problems == ['weather 150 ft / 2000 m, below the minima of every available approach '
                                      '(best: ILS 18, 200 ft / 550 m)']


def test_weather_exactly_at_minima_is_enough(tmp_path):
    found = check(tmp_path, airports={'XAAA': (2500, [ILS])}, weather={'XAAA': (200, 550)})
    assert found['XAAA'].problems == []


def test_an_unserviceable_approach_does_not_count(tmp_path):
    found = check(tmp_path, airports={'XAAA': (2500, [ILS, ('RNAV 18', 400, 1500)])}, weather={'XAAA': (300, 1000)},
                  notams=[('XAAA', 'approach_unserviceable', 'ILS 18')])
    assert 'below the minima' in found['XAAA'].problems[0] and 'RNAV 18' in found['XAAA'].problems[0]


def test_a_short_runway(tmp_path):
    found = check(tmp_path, airports={'XAAA': (1500, [ILS])}, weather={'XAAA': (1000, 5000)})
    assert found['XAAA'].problems == ['longest runway 1500 m, under the 1900 m required']


def test_not_enough_fuel(tmp_path):
    found = check(tmp_path, airports={'XAAA': (2500, [ILS])}, weather={'XAAA': (1000, 5000)}, fuel_kg=3000,
                  minutes={'XAAA': 50})
    assert found['XAAA'].problems == ['arrives with 1000 kg, under the 1200 kg required on landing']


def test_a_closed_airport(tmp_path):
    found = check(tmp_path, airports={'XAAA': (2500, [ILS])}, weather={'XAAA': (1000, 5000)},
                  notams=[('XAAA', 'airport_closed', None)])
    assert found['XAAA'].problems == ['closed (N0)']


def test_nearest_first(tmp_path):
    feeds = make_feeds(tmp_path, {'XAAA': (2500, [ILS]), 'XBBB': (2500, [ILS])},
                       {'XAAA': (1000, 5000), 'XBBB': (1000, 5000)}, minutes={'XAAA': 40, 'XBBB': 20})
    assert [option.icao for option in options(feeds.flight('T100'), feeds)] == ['XBBB', 'XAAA']
    assert assess('XAAA', feeds.flight('T100'), feeds).minutes == 40
