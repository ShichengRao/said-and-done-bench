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


def test_report_layout():
    feeds = [Feed('KST', [Reading(utc(11, 2, 6), 2.0), Reading(utc(11, 3, 0), 0.5)],
                  flagged=[utc(11, 4, 0)] * 1 + [utc(11, 5, 0)], missing=[utc(11, 6, 0)]),
             Feed('HWP', [Reading(utc(11, 1, 0), 3.0), Reading(utc(11, 2, 6), 1.0), Reading(utc(11, 2, 7), 2.0)])]
    assert monthly_report(feeds, STATIONS, '2026-11') == (
        'Tide report for 2026-11 (station local time)\n'
        '\n'
        'station              readings  flagged  missing  high (m)               high at  low (m)                low at  mean (m)\n'
        '-------------------  --------  -------  -------  --------  --------------------  -------  --------------------  --------\n'
        'Harlow Point (HWP)          3        0        0     3.000  2026-11-01 00:00 GMT    1.000  2026-11-02 06:00 GMT     2.000\n'
        'Kestrel Sound (KST)         2        2        1     2.000  2026-11-02 11:30 IST    0.500  2026-11-03 05:30 IST     1.250\n'
    )


def test_report_counts_each_instant_once():
    """A restarted gauge re-sends its last rows, so a station's files overlap."""
    feeds = [Feed('OWL', [Reading(utc(11, 1, 6), 1.25), Reading(utc(11, 9, 15), 0.25)], flagged=[utc(11, 9, 16)],
                  missing=[utc(11, 9, 17)]),
             Feed('OWL', [Reading(utc(11, 9, 15), 0.25), Reading(utc(11, 20, 9), 1.5)],
                  flagged=[utc(11, 9, 16), utc(11, 21, 0)], missing=[utc(11, 9, 17)])]
    assert station_line(monthly_report(feeds, STATIONS, '2026-11'), 'OWL') == [
        '3', '2', '1', '1.500', '2026-11-20', '05:00', 'AST', '0.250', '2026-11-09', '11:00', 'AST', '1.000']
