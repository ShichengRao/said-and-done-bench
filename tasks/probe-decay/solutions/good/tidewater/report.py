"""The monthly tide report, in each station's local time."""

from __future__ import annotations

import datetime as dt

import textable

from tidewater.model import Feed
from tidewater.stations import Station
from tidewater.zones import zone

HEADERS = ['station', 'readings', 'flagged', 'missing', 'high (m)', 'high at', 'low (m)', 'low at', 'mean (m)']
ALIGN = '<>>>>>>>>'


def local_month(station: Station, month: str) -> tuple[dt.datetime, dt.datetime]:
    """The UTC instants where the station's local calendar month ('2026-11') starts and ends."""
    year, number = map(int, month.split('-'))
    station_zone = zone(station.tz)
    start = station_zone.to_utc(dt.datetime(year, number, 1))
    end = station_zone.to_utc(dt.datetime(year + number // 12, number % 12 + 1, 1))
    return start, end


def local_time(station: Station, at: dt.datetime) -> str:
    station_zone = zone(station.tz)
    return f'{station_zone.to_local(at):%Y-%m-%d %H:%M} {station_zone.abbreviation(at)}'


def merge(feeds: list[Feed]) -> dict[str, Feed]:
    """One feed per station, each instant once: a station's files can overlap."""
    merged: dict[str, Feed] = {}
    for feed in feeds:
        into = merged.setdefault(feed.station, Feed(feed.station, []))
        seen = {r.at for r in into.readings}
        into.readings += [r for r in feed.readings if r.at not in seen and not seen.add(r.at)]
        into.flagged += [at for at in feed.flagged if at not in into.flagged]
        into.missing += [at for at in feed.missing if at not in into.missing]
    return merged


def month_rows(feed: Feed, station: Station, month: str) -> Feed:
    """The station's rows inside its local month, readings oldest first."""
    start, end = local_month(station, month)
    return Feed(feed.station, sorted((r for r in feed.readings if start <= r.at < end), key=lambda r: r.at),
                [at for at in feed.flagged if start <= at < end], [at for at in feed.missing if start <= at < end])


def monthly_report(feeds: list[Feed], stations: dict[str, Station], month: str) -> str:
    """One line per station: its readings in its local month, high and low water, and mean level."""
    rows = []
    by_station = merge(feeds)
    for code in sorted(by_station, key=lambda code: stations[code].name):
        station = stations[code]
        inside = month_rows(by_station[code], station, month)
        if not inside.readings:
            continue
        high = max(inside.readings, key=lambda r: r.level_m)
        low = min(inside.readings, key=lambda r: r.level_m)
        mean = sum(r.level_m for r in inside.readings) / len(inside.readings)
        rows.append([
            f'{station.name} ({code})', len(inside.readings), len(inside.flagged), len(inside.missing),
            f'{high.level_m:.3f}', local_time(station, high.at),
            f'{low.level_m:.3f}', local_time(station, low.at), f'{mean:.3f}',
        ])
    table = textable.render(HEADERS, rows, align=ALIGN)
    return f'Tide report for {month} (station local time)\n\n{table}\n'
