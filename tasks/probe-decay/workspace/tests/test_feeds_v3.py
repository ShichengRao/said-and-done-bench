"""v3 feeds (docs/feed-v3.md)."""

import datetime as dt
from pathlib import Path

import pytest

from tidewater.feeds import FeedError, load_feed
from tidewater.stations import load_stations

STATIONS = load_stations(Path(__file__).resolve().parent.parent / 'data' / 'stations.json')
UTC = dt.timezone.utc


def v3(tmp_path, header, *rows):
    path = tmp_path / 'feed.csv'
    path.write_text('#tidewater-feed v3\n' + ''.join(f'#{line}\n' for line in header)
                    + 'observed_at,level,quality\n' + ''.join(f'{row}\n' for row in rows))
    return path


def test_v3_header_and_millimetres(tmp_path):
    feed = load_feed(v3(tmp_path, ['station: KST', 'units: mm', 'datum: CD'], '2027-01-15 05:30,3412,G'), STATIONS)
    assert feed.station == 'KST' and feed.flagged == [] and feed.missing == []
    (reading,) = feed.readings
    assert reading.at == dt.datetime(2027, 1, 15, 0, 0, tzinfo=UTC)  # Kestrel Sound is UTC+5:30
    assert reading.level_m == pytest.approx(3.412)


def test_v3_header_keys_come_in_any_order(tmp_path):
    path = v3(tmp_path, ['datum: CD', 'units: cm', 'station: KST'], '2027-01-15 05:30,341.2,G')
    assert load_feed(path, STATIONS).readings[0].level_m == pytest.approx(3.412)


@pytest.mark.parametrize('units, level, metres', [('mm', '1250', 1.25), ('cm', '125.0', 1.25), ('ft', '11.25', 3.429)])
def test_v3_units(tmp_path, units, level, metres):
    path = v3(tmp_path, ['station: KST', f'units: {units}', 'datum: CD'], f'2027-01-15 05:30,{level},G')
    assert load_feed(path, STATIONS).readings[0].level_m == pytest.approx(metres)


def test_v3_levels_from_mean_sea_level_are_converted_to_chart_datum(tmp_path):
    # Owlfen Bar's mean sea level is 1.875 m above its chart datum.
    path = v3(tmp_path, ['station: OWL', 'units: ft', 'datum: MSL'], '2027-01-15 20:00,1.50,G', '2027-01-15 21:00,-2.00,G')
    assert [r.level_m for r in load_feed(path, STATIONS).readings] == pytest.approx([2.3322, 1.2654])


def test_v3_calibration_offset_is_added_in_the_files_units(tmp_path):
    path = v3(tmp_path, ['station: KST', 'units: cm', 'datum: CD', 'offset: -2.5'], '2027-01-15 05:30,125.0,G')
    assert load_feed(path, STATIONS).readings[0].level_m == pytest.approx(1.225)
    path = v3(tmp_path, ['offset: 12', 'station: OWL', 'datum: MSL', 'units: mm'], '2027-01-15 20:00,-500,G')
    assert load_feed(path, STATIONS).readings[0].level_m == pytest.approx(1.387)


def test_v3_only_good_rows_are_readings(tmp_path):
    path = v3(tmp_path, ['station: KST', 'units: mm', 'datum: CD'],
              '2027-01-15 05:30,1200,G', '2027-01-15 06:30,9100,S', '2027-01-15 07:30,-400,B',
              '2027-01-15 08:30,,M', '2027-01-15 09:30,1310,G')
    feed = load_feed(path, STATIONS)
    assert [r.level_m for r in feed.readings] == pytest.approx([1.2, 1.31])
    assert feed.flagged == [dt.datetime(2027, 1, 15, 1, 0, tzinfo=UTC), dt.datetime(2027, 1, 15, 2, 0, tzinfo=UTC)]
    assert feed.missing == [dt.datetime(2027, 1, 15, 3, 0, tzinfo=UTC)]


def test_v3_local_time_follows_the_stations_zone(tmp_path):
    path = v3(tmp_path, ['station: CMY', 'units: cm', 'datum: CD'], '2027-07-01 12:00,150.0,G', '2027-12-01 12:00,150.0,G')
    assert [r.at for r in load_feed(path, STATIONS).readings] == [
        dt.datetime(2027, 7, 1, 14, 30, tzinfo=UTC),  # NDT, UTC-2:30
        dt.datetime(2027, 12, 1, 15, 30, tzinfo=UTC),  # NST, UTC-3:30
    ]


def test_v3_repeated_hour_when_the_clocks_go_back(tmp_path):
    path = v3(tmp_path, ['station: CMY', 'units: cm', 'datum: CD'],
              '2027-11-07 00:00,150.0,G', '2027-11-07 01:00,151.0,G', '2027-11-07 01:00,,M', '2027-11-07 02:00,153.0,G')
    feed = load_feed(path, STATIONS)
    assert [r.at for r in feed.readings] == [dt.datetime(2027, 11, 7, 2, 30, tzinfo=UTC),
                                             dt.datetime(2027, 11, 7, 3, 30, tzinfo=UTC),
                                             dt.datetime(2027, 11, 7, 5, 30, tzinfo=UTC)]
    assert feed.missing == [dt.datetime(2027, 11, 7, 4, 30, tzinfo=UTC)]


def test_v3_unknown_units_are_rejected(tmp_path):
    with pytest.raises(FeedError):
        load_feed(v3(tmp_path, ['station: KST', 'units: fathoms', 'datum: CD'], '2027-01-15 05:30,2,G'), STATIONS)
