import datetime as dt
from pathlib import Path

import pytest

from tidewater.feeds import FeedError, load_feed
from tidewater.stations import load_stations

STATIONS = load_stations(Path(__file__).resolve().parent.parent / 'data' / 'stations.json')
UTC = dt.timezone.utc


def v2(tmp_path, code, *rows):
    path = tmp_path / 'feed.csv'
    path.write_text(f'# tidewater feed v2\n# station: {code}\ntime,level_cm\n' + ''.join(f'{row}\n' for row in rows))
    return path


def test_v2_levels_in_metres_and_times_in_utc(tmp_path):
    feed = load_feed(v2(tmp_path, 'HWP', '15/01/2027 00:00,312.4', '15/01/2027 01:00,298.0'), STATIONS)
    assert feed.station == 'HWP'
    assert [r.at for r in feed.readings] == [dt.datetime(2027, 1, 15, 0, tzinfo=UTC), dt.datetime(2027, 1, 15, 1, tzinfo=UTC)]
    assert [r.level_m for r in feed.readings] == pytest.approx([3.124, 2.98])


def test_v2_local_time_follows_the_stations_zone(tmp_path):
    (summer,) = load_feed(v2(tmp_path, 'BRK', '01/07/2027 12:00,87.5'), STATIONS).readings
    assert summer.at == dt.datetime(2027, 7, 1, 16, 0, tzinfo=UTC)  # EDT
    (winter,) = load_feed(v2(tmp_path, 'BRK', '15/01/2027 12:00,87.5'), STATIONS).readings
    assert winter.at == dt.datetime(2027, 1, 15, 17, 0, tzinfo=UTC)  # EST


def test_v2_repeated_hour_when_the_clocks_go_back(tmp_path):
    rows = ['07/11/2027 00:00,80.0', '07/11/2027 01:00,81.0', '07/11/2027 01:00,82.0', '07/11/2027 02:00,83.0']
    assert [r.at for r in load_feed(v2(tmp_path, 'BRK', *rows), STATIONS).readings] == [
        dt.datetime(2027, 11, 7, hour, tzinfo=UTC) for hour in (4, 5, 6, 7)]


def test_unknown_format_is_rejected(tmp_path):
    path = tmp_path / 'feed.csv'
    path.write_text('# tidewater feed v9\n# station: HWP\n')
    with pytest.raises(FeedError):
        load_feed(path, STATIONS)


def test_unregistered_station_is_rejected(tmp_path):
    with pytest.raises(FeedError):
        load_feed(v2(tmp_path, 'ZZZ'), STATIONS)
