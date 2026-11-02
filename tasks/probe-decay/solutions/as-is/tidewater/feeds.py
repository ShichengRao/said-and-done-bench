"""Reading gauge feed files (docs/feeds.md, docs/feed-v3.md)."""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import chronoparse

from tidewater.model import Feed, Reading
from tidewater.stations import Station
from tidewater.zones import zone

METRES_PER_UNIT = {'mm': 0.001, 'cm': 0.01, 'ft': 0.3048}
DATUMS = ('CD', 'MSL')


class FeedError(ValueError):
    """A feed file that can't be read."""


def load_feed(path: Path, stations: dict[str, Station]) -> Feed:
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    if not lines:
        raise FeedError(f'{path}: empty file')
    if lines[0].strip() == '# tidewater feed v2':
        return _load_v2(path, lines[1:], stations)
    if lines[0].strip() == '#tidewater-feed v3':
        return _load_v3(path, lines[1:], stations)
    raise FeedError(f'{path}: unsupported feed format {lines[0].strip()!r}')


def _station(path: Path, code: str, stations: dict[str, Station]) -> Station:
    if code not in stations:
        raise FeedError(f'{path}: station {code!r} is not in the registry')
    return stations[code]


class _Clock:
    """A file's local wall-clock times to UTC, row by row."""

    def __init__(self, path: Path, station: Station) -> None:
        self.path, self.zone, self.previous = path, zone(station.tz), None

    def utc(self, text: str) -> dt.datetime:
        local = chronoparse.parse_local(text)
        # When the clocks go back, the repeated hour comes twice: daylight time, then standard.
        fold = 1 if self.previous is not None and local <= self.previous else 0
        self.previous = local
        try:
            return self.zone.to_utc(local, fold=fold)
        except chronoparse.NonexistentTimeError as error:
            raise FeedError(f'{self.path}: {error}') from None


def _load_v2(path: Path, lines: list[str], stations: dict[str, Station]) -> Feed:
    """v2: '# station: CODE', then rows of local wall-clock time and level in cm."""
    key, _, code = lines[0].lstrip('# ').partition(':')
    if key.strip() != 'station':
        raise FeedError(f'{path}: expected a "# station:" line, got {lines[0]!r}')
    station = _station(path, code.strip(), stations)
    clock = _Clock(path, station)
    return Feed(station.code, [Reading(clock.utc(row['time']), float(row['level_cm']) / 100)
                               for row in csv.DictReader(lines[1:])])


def _v3_header(path: Path, lines: list[str]) -> tuple[dict[str, str], list[str]]:
    header = {}
    for index, line in enumerate(lines):
        if not line.startswith('#'):
            return header, lines[index:]
        key, separator, value = line.lstrip('#').partition(':')
        if not separator:
            raise FeedError(f'{path}: expected "#key: value", got {line!r}')
        header[key.strip()] = value.strip()
    return header, []


def _load_v3(path: Path, lines: list[str], stations: dict[str, Station]) -> Feed:
    header, rows = _v3_header(path, lines)
    station = _station(path, header.get('station', ''), stations)
    units, datum = header.get('units'), header.get('datum')
    if units not in METRES_PER_UNIT or datum not in DATUMS:
        raise FeedError(f'{path}: unknown units {units!r} or datum {datum!r}')
    correction = float(header.get('offset', '0'))
    base = station.msl_above_cd_m if datum == 'MSL' else 0.0
    clock = _Clock(path, station)
    feed = Feed(station.code, [])
    for row in csv.DictReader(rows):
        at = clock.utc(row['observed_at'])
        quality = row['quality'].strip()
        if quality == 'G':
            feed.readings.append(Reading(at, (float(row['level']) + correction) * METRES_PER_UNIT[units] + base))
        elif quality in ('S', 'B'):
            feed.flagged.append(at)
        elif quality == 'M':
            feed.missing.append(at)
        else:
            raise FeedError(f'{path}: unknown quality {quality!r}')
    return feed
