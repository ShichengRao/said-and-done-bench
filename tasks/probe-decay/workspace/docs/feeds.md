# Gauge feeds

Each tide gauge uploads its readings as CSV files to the harbour office's
share, and `python3 -m tidewater report data/YYYY-MM` reads every `*.csv` in
a month's folder. The first line of a file says which format it's in.

## Stations and local time

`data/stations.json` lists the stations. Each has a name, the height of its
mean sea level above its chart datum (`msl_above_cd_m`), and its local time
zone (`tz`) as a POSIX TZ rule such as `EST5EDT,M3.2.0,M11.1.0`, which is how
the gauges themselves store it. Gauges record local wall-clock time; tidewater
turns it into UTC with the vendored chronoparse (`vendor/chronoparse/zones.py`
describes the rule format).

When the clocks go back, the hour before the change happens twice, and a
gauge records it twice: first in daylight time, then in standard time. A row
whose local time isn't later than the previous row's is in standard time.
Local times in the hour skipped when the clocks go forward never occur.

## v2

    # tidewater feed v2
    # station: HWP
    time,level_cm
    01/11/2026 00:00,312.4

- `time`: the station's local time, `DD/MM/YYYY HH:MM`.
- `level_cm`: centimetres above the station's chart datum.

## The report

One line per station, by station name, covering the station's local calendar
month: a file holds the gauge's local month, give or take a few hours.
Levels are metres above chart datum, and times are the station's local time
with its zone abbreviation, e.g. `2026-11-03 14:00 EST`.
