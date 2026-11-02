"""The monthly tide report, in each station's local time."""

from __future__ import annotations

import datetime as dt

import chronoparse
import textable

from tidewater.model import Feed
from tidewater.stations import Station

HEADERS = ['station', 'readings', 'high (m)', 'high at', 'low (m)', 'low at', 'mean (m)']
ALIGN = '<>>>>>>'


def local_month(station: Station, month: str) -> tuple[dt.datetime, dt.datetime]:
    """The UTC instants where the station's local calendar month ('2026-11') starts and ends."""
    year, number = map(int, month.split('-'))
    zone = chronoparse.zone(station.tz)
    start = zone.to_utc(dt.datetime(year, number, 1))
    end = zone.to_utc(dt.datetime(year + number // 12, number % 12 + 1, 1))
    return start, end


def local_time(station: Station, at: dt.datetime) -> str:
    zone = chronoparse.zone(station.tz)
    return f'{zone.to_local(at):%Y-%m-%d %H:%M} {zone.abbreviation(at)}'


def monthly_report(feeds: list[Feed], stations: dict[str, Station], month: str) -> str:
    """One line per station: its readings in its local month, high and low water, and mean level."""
    by_station: dict[str, Feed] = {}
    for feed in feeds:
        if feed.station in by_station:
            raise ValueError(f'more than one feed for station {feed.station}')
        by_station[feed.station] = feed
    rows = []
    for code in sorted(by_station, key=lambda code: stations[code].name):
        station = stations[code]
        start, end = local_month(station, month)
        inside = sorted((r for r in by_station[code].readings if start <= r.at < end), key=lambda r: r.at)
        if not inside:
            continue
        high = max(inside, key=lambda r: r.level_m)
        low = min(inside, key=lambda r: r.level_m)
        mean = sum(r.level_m for r in inside) / len(inside)
        rows.append([
            f'{station.name} ({code})', len(inside),
            f'{high.level_m:.3f}', local_time(station, high.at),
            f'{low.level_m:.3f}', local_time(station, low.at), f'{mean:.3f}',
        ])
    table = textable.render(HEADERS, rows, align=ALIGN)
    return f'Tide report for {month} (station local time)\n\n{table}\n'
