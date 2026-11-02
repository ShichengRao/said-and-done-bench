import datetime as dt
from pathlib import Path

from tidewater.model import Feed, Reading
from tidewater.report import monthly_report
from tidewater.stations import load_stations

STATIONS = load_stations(Path(__file__).resolve().parent.parent / 'data' / 'stations.json')
UTC = dt.timezone.utc


def utc(month, day, hour, minute=0):
    return dt.datetime(2026, month, day, hour, minute, tzinfo=UTC)


def station_line(report, code):
    (line,) = [line for line in report.splitlines() if f'({code})' in line]
    return line.split(f'({code})')[1].split()


def test_report_covers_the_stations_local_month():
    # Kestrel Sound is UTC+5:30: its November runs from 18:30 UTC on October 31.
    readings = [Reading(at, 1.0) for at in (utc(10, 31, 18, 0), utc(10, 31, 18, 30), utc(11, 30, 18, 29),
                                            utc(11, 30, 18, 30))]
    assert station_line(monthly_report([Feed('KST', readings)], STATIONS, '2026-11'), 'KST')[0] == '2'
