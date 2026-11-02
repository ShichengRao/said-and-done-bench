# Feed format v3

From Harbour Operations (Ines Varga), October 2026. The gauges replaced since
July (Kestrel Sound, Owlfen Bar, Cape Mercy, and Vesper Reef once it's
commissioned) send this format instead of v2. The monthly report should
cover v2 and v3 stations alike.

    #tidewater-feed v3
    #station: CMY
    #units: cm
    #datum: CD
    #offset: 1.5
    observed_at,level,quality
    2026-11-01 00:00,154.2,G
    2026-11-01 01:00,,M

Header lines start with `#`. The first is always `#tidewater-feed v3`; the
others are `key: value` pairs, in any order:

- `station`: the station's code in `data/stations.json`.
- `units`: `mm`, `cm`, or `ft` (1 ft = 0.3048 m exactly).
- `datum`: what `level` is measured from: `CD`, the station's chart datum (as
  in v2), or `MSL`, its mean sea level. The report gives every level in
  metres above chart datum, so for `MSL` add the station's `msl_above_cd_m`.
- `offset` (optional): the sensor's calibration correction, in `units`,
  added to every level. Missing means 0.

Columns:

- `observed_at`: the station's local wall-clock time, `YYYY-MM-DD HH:MM`, as
  for v2 (see "Stations and local time" in `docs/feeds.md`, including the
  repeated hour when the clocks go back).
- `level`: in `units`, measured from `datum`; empty when `quality` is `M`.
- `quality`: `G` good, `S` suspect, `B` bad, or `M` missing. Only `G` rows
  are readings: they alone count toward the report's readings, high and low
  water, and mean. `S` and `B` rows are *flagged*; `M` rows are *missing*.

A gauge may split a month across several files, after a restart or a sensor
swap (`CMY-2026-11a.csv`, `CMY-2026-11b.csv`). The files can overlap, because
a restarted gauge re-sends its last few rows: count each instant once.

## Report changes

Two new columns after `readings`: `flagged` and `missing`, how many of the
station's rows in its local month were flagged or missing, each instant
counted once (always 0 for v2 stations).

## Export

`python3 -m tidewater export FOLDER --station CODE` prints one station's
readings for the month as CSV, oldest first, one line per instant:

    utc,local,level_m
    2026-11-01T03:30Z,2026-11-01 00:00 NDT,1.557

- `utc`: the instant in UTC, `YYYY-MM-DDTHH:MMZ`.
- `local`: the station's local time and zone abbreviation, as in the report.
- `level_m`: metres above chart datum, to 3 decimals.

Like the report, it covers the station's local month (the folder's name, or
`--month YYYY-MM`) and only `G` rows.
