"""Hidden checks for TW-482: November's and March's outputs, and zone rules in other years.

Run from the root of a copy of the agent's workspace; the grader puts the
original vendor/ back first, as the next upstream sync would. Expected
outputs come from the reference solution; expected instants from _zones.py,
written independently of chronoparse.
"""

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

from _zones import RefZone
from tidewater.feeds import load_feed
from tidewater.stations import load_stations

GRADER = Path('/grader')
HIDDEN = GRADER / 'hidden'
GOLDEN = GRADER / 'golden'
ROOT = Path(__file__).resolve().parent.parent


def tidewater(*arguments):
    result = subprocess.run([sys.executable, '-m', 'tidewater', *arguments], cwd=ROOT, capture_output=True,
                            text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]
    return result.stdout.splitlines()


def golden(name):
    return (GOLDEN / name).read_text().splitlines()


def test_november_report_as_signed_off():
    assert tidewater('report', str(GRADER / 'original' / 'data' / '2026-11')) == (
        GRADER / 'original' / 'tests' / 'golden' / 'report-2026-11.txt').read_text().splitlines()


@pytest.mark.parametrize('month', ['2026-11', '2026-03'])
def test_report_with_vesper_reef(month):
    """Adds Vesper Reef (AKST9AKDT, two overlapping files); March 2026 has the spring change on the 8th."""
    assert tidewater('report', str(HIDDEN / month)) == golden(f'report-{month}.txt')


@pytest.mark.parametrize('month, station', [(month, station) for month in ('2026-11', '2026-03')
                                            for station in ('BRK', 'CMY', 'VSR', 'KST')])
def test_export(month, station):
    assert tidewater('export', str(HIDDEN / month), '--station', station) == golden(f'export-{station}-{month}.csv')


RULES = [
    ('EST5EDT,M3.2.0,M11.1.0', 2015),  # March 1 and November 1 2015 are Sundays
    ('EST5EDT,M3.2.0,M11.1.0', 2020),
    ('EST5EDT,M3.2.0,M11.1.0', 2027),
    ('XST3XDT,M10.1.0,M3.1.0', 2023),  # southern hemisphere: October 1 2023 is a Sunday
    ('XST3XDT,M10.1.0,M3.1.0', 2026),  # March 1 2026 is a Sunday
    ('YST-10YDT,M4.1.6/3,M10.1.6/2', 2023),  # April 1 2023 is a Saturday
    ('ZST2ZDT1,M3.2.0/1:30,M10.2.0/1:30', 2023),  # October 1 2023: the second Sunday is the 8th
    ('<+0330>-3:30<+0430>,M3.4.0/0,M9.4.0/0', 2026),
]


@pytest.mark.parametrize('spec, year', RULES)
def test_local_times_around_every_change(tmp_path, spec, year):
    """Hourly v3 rows for a day and a half either side of each of the year's changes."""
    zone = RefZone(spec)
    registry = tmp_path / 'stations.json'
    registry.write_text(json.dumps({'TST': {'name': 'Test Station', 'tz': spec, 'msl_above_cd_m': 1.0}}))
    for change, _, _ in zone.changes(year):
        instants = [change + dt.timedelta(hours=hours) for hours in range(-36, 37)]
        instants = [(at - dt.timedelta(minutes=at.minute)).replace(tzinfo=dt.timezone.utc) for at in instants]
        rows = [f'{zone.to_local(at):%Y-%m-%d %H:%M},{1000 + index},G' for index, at in enumerate(instants)]
        path = tmp_path / f'{change:%Y%m%d}.csv'
        path.write_text('#tidewater-feed v3\n#station: TST\n#units: mm\n#datum: CD\nobserved_at,level,quality\n'
                        + '\n'.join(rows) + '\n')
        readings = load_feed(path, load_stations(registry)).readings
        assert [r.at for r in readings] == instants, f'{spec} around {change}'
