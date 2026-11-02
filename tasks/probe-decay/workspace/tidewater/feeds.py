"""Reading gauge feed files (docs/feeds.md)."""

from __future__ import annotations

import csv
from pathlib import Path

import chronoparse

from tidewater.model import Feed, Reading
from tidewater.stations import Station


class FeedError(ValueError):
    """A feed file that can't be read."""


def load_feed(path: Path, stations: dict[str, Station]) -> Feed:
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    if not lines:
        raise FeedError(f'{path}: empty file')
    if lines[0].strip() == '# tidewater feed v2':
        return _load_v2(path, lines[1:], stations)
    raise FeedError(f'{path}: unsupported feed format {lines[0].strip()!r}')


def _station(path: Path, code: str, stations: dict[str, Station]) -> Station:
    if code not in stations:
        raise FeedError(f'{path}: station {code!r} is not in the registry')
    return stations[code]


def _load_v2(path: Path, lines: list[str], stations: dict[str, Station]) -> Feed:
    """v2: '# station: CODE', then rows of local wall-clock time and level in cm."""
    key, _, code = lines[0].lstrip('# ').partition(':')
    if key.strip() != 'station':
        raise FeedError(f'{path}: expected a "# station:" line, got {lines[0]!r}')
    station = _station(path, code.strip(), stations)
    zone = chronoparse.zone(station.tz)
    readings = []
    previous = None
    for row in csv.DictReader(lines[1:]):
        local = chronoparse.parse_local(row['time'])
        # When the clocks go back, the repeated hour comes twice: daylight time, then standard.
        fold = 1 if previous is not None and local <= previous else 0
        try:
            at = zone.to_utc(local, fold=fold)
        except chronoparse.NonexistentTimeError as error:
            raise FeedError(f'{path}: {error}') from None
        readings.append(Reading(at, float(row['level_cm']) / 100))
        previous = local
    return Feed(station.code, readings)
