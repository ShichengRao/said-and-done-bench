"""python3 -m tidewater export: one station's readings for a month, as CSV."""

from __future__ import annotations

from tidewater.model import Feed
from tidewater.report import local_time, merge, month_rows
from tidewater.stations import Station


def export_csv(feeds: list[Feed], stations: dict[str, Station], month: str, code: str) -> str:
    merged = merge(feeds)
    if code not in merged:
        raise ValueError(f'no feed for station {code}')
    station = stations[code]
    lines = ['utc,local,level_m']
    lines += [f'{r.at:%Y-%m-%dT%H:%MZ},{local_time(station, r.at)},{r.level_m:.3f}'
              for r in month_rows(merged[code], station, month).readings]
    return '\n'.join(lines) + '\n'
