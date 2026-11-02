"""Generates the feed files: November 2026 for the workspace, March and November 2026 for the hidden checks.

    python3 make_data.py OUT_DIR 2026-11            # writes OUT_DIR/2026-11/*.csv
    python3 make_data.py OUT_DIR 2026-11 --hidden   # the hidden set (adds Vesper Reef)

Deterministic. Each station gets hourly readings for its local month, give
or take a few hours at each end, written as local wall-clock times with the
grader's own time zone code (grader/hidden_tests/_zones.py), so the repeated
hour when the clocks go back appears twice. Levels: two tidal constituents, a
spring-neap cycle, noise, and for the stations whose zone chronoparse gets
wrong that month, a storm surge in the week it misdates, so their high water
falls there. Some v3 rows are flagged or missing, and one suspect and one bad
row are spikes that would become the month's high and low if they weren't
left out. A station's seed is bumped until its high and low are unique among
good readings and its mean isn't within 1e-4 of a rounding boundary, so the
report can't depend on the order readings are summed or compared in.

The workspace's data/2026-11 and the grader's hidden/ folders were made with
this; the tests check they're unchanged.
"""

import datetime as dt
import json
import math
import random
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / 'grader' / 'hidden_tests'))
from _zones import RefZone  # noqa: E402

STATIONS = json.loads((TASK / 'workspace' / 'data' / 'stations.json').read_text())
FOOT = 0.3048
FACTOR = {'mm': 0.001, 'cm': 0.01, 'ft': FOOT}
DECIMALS = {'mm': 0, 'cm': 1, 'ft': 2}

# code: (feed version, units, datum, calibration offset in units or None, files, tidal range in m)
SPECS = {
    'HWP': (2, 'cm', 'CD', None, 1, 1.45),
    'BRK': (2, 'cm', 'CD', None, 1, 1.0),
    'KST': (3, 'mm', 'CD', 12, 1, 0.68),
    'OWL': (3, 'ft', 'MSL', -0.05, 1, 1.25),
    'CMY': (3, 'cm', 'CD', 1.5, 2, 0.6),
    'VSR': (3, 'mm', 'MSL', None, 2, 0.42),
}
VISIBLE = ('HWP', 'BRK', 'KST', 'OWL', 'CMY')
# The week chronoparse misdates in each month, as local dates: [first day, last day].
SURGE_WEEK = {'2026-11': (dt.datetime(2026, 11, 2), dt.datetime(2026, 11, 7)),
              '2026-03': (dt.datetime(2026, 3, 9), dt.datetime(2026, 3, 14))}
MISDATED = ('BRK', 'CMY', 'VSR')  # zones with M3.2.0 / M11.1.0 rules


def month_bounds(month):
    year, number = map(int, month.split('-'))
    return dt.datetime(year, number, 1), dt.datetime(year + number // 12, number % 12 + 1, 1)


def series(month, code, attempt):
    version, units, datum, correction, files, amplitude = SPECS[code]
    zone = RefZone(STATIONS[code]['tz'])
    rng = random.Random(f'{code}:{month}:{attempt}')
    msl = STATIONS[code]['msl_above_cd_m']
    first, last = month_bounds(month)
    start, end = zone.to_utc(first), zone.to_utc(last)
    phase, diurnal, neap = rng.uniform(0, 12.42), rng.uniform(0, 24.84), rng.uniform(0, 14.77)
    surge = None
    if code in MISDATED:
        low_day, high_day = SURGE_WEEK[month]
        surge = zone.to_utc(low_day + dt.timedelta(hours=rng.uniform(12, (high_day - low_day).days * 24)))
    rows = []
    at, stop = start - dt.timedelta(hours=rng.randrange(1, 4)), end + dt.timedelta(hours=rng.randrange(1, 4))
    while at < stop:
        hours = (at - start).total_seconds() / 3600
        level = (msl + amplitude * (1 + 0.3 * math.cos(2 * math.pi * (hours / 24 - neap) / 14.77))
                 * math.cos(2 * math.pi * (hours - phase) / 12.4206)
                 + 0.12 * math.cos(2 * math.pi * (hours - diurnal) / 24.84) + rng.gauss(0, 0.02))
        if surge is not None:
            level += 0.45 * math.exp(-(((at - surge).total_seconds() / 3600) / 9) ** 2)
        draw = rng.random()
        quality = 'G' if version == 2 else 'S' if draw < 0.015 else 'B' if draw < 0.025 else 'M' if draw < 0.035 else 'G'
        rows.append([at, zone.to_local(at), round(level, 3), quality])
        at += dt.timedelta(hours=1)
    if version == 3:
        good = [row[2] for row in rows if row[3] == 'G']
        rows[len(rows) // 3][2:] = [round(max(good) + rng.uniform(0.4, 0.9), 3), 'S']
        rows[2 * len(rows) // 3][2:] = [round(min(good) - rng.uniform(0.3, 0.6), 3), 'B']
    return rows, start, end


def level_text(code, level_cd):
    version, units, datum, correction, *_ = SPECS[code]
    if version == 2:
        return f'{level_cd * 100:.1f}'
    base = STATIONS[code]['msl_above_cd_m'] if datum == 'MSL' else 0.0
    value = round((level_cd - base) / FACTOR[units] - (correction or 0), DECIMALS[units])
    return str(int(value)) if units == 'mm' else f'{value:.{DECIMALS[units]}f}'


def level_back(code, text):
    """What a correct reader makes of a level in the file: metres above chart datum."""
    version, units, datum, correction, *_ = SPECS[code]
    if version == 2:
        return float(text) / 100
    base = STATIONS[code]['msl_above_cd_m'] if datum == 'MSL' else 0.0
    return (float(text) + (correction or 0)) * FACTOR[units] + base


def acceptable(code, rows, start, end):
    shown = [round(level_back(code, level_text(code, level)), 6)
             for at, _, level, quality in rows if quality == 'G' and start <= at < end]
    mean = sum(shown) / len(shown)
    return (shown.count(max(shown)) == 1 and shown.count(min(shown)) == 1 and min(shown) > 0
            and abs((mean * 1000) % 1 - 0.5) > 1e-4)


def render(month, code, rows):
    version, units, datum, correction, files, _ = SPECS[code]
    if version == 2:
        lines = ['# tidewater feed v2', f'# station: {code}', 'time,level_cm']
        lines += [f'{local:%d/%m/%Y %H:%M},{level_text(code, level)}' for _, local, level, _ in rows]
        return {f'{code}-{month}.csv': '\n'.join(lines) + '\n'}
    header = ['#tidewater-feed v3', f'#station: {code}', f'#units: {units}', f'#datum: {datum}']
    if correction is not None:
        header.append(f'#offset: {correction}')
    body = [f'{local:%Y-%m-%d %H:%M},{"" if quality == "M" else level_text(code, level)},{quality}'
            for _, local, level, quality in rows]
    columns = 'observed_at,level,quality'
    if files == 1:
        return {f'{code}-{month}.csv': '\n'.join(header + [columns] + body) + '\n'}
    split = len(body) // 2 + 12
    # The restarted gauge re-sends its last three rows, and lists its header keys in another order.
    second = [header[0], *reversed(header[1:])]
    return {f'{code}-{month}a.csv': '\n'.join(header + [columns] + body[:split]) + '\n',
            f'{code}-{month}b.csv': '\n'.join(second + [columns] + body[split - 3:]) + '\n'}


def main(out_dir, month, hidden=False):
    folder = Path(out_dir) / month
    folder.mkdir(parents=True, exist_ok=True)
    for code in (SPECS if hidden else VISIBLE):
        for attempt in range(200):
            rows, start, end = series(month, code, attempt)
            if acceptable(code, rows, start, end):
                break
        else:
            raise SystemExit(f'{code}: no acceptable series in 200 attempts')
        for name, text in render(month, code, rows).items():
            (folder / name).write_text(text)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], '--hidden' in sys.argv[3:])
