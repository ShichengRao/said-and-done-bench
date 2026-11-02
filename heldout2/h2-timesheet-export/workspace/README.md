# timesheets

The hours staff log against projects, and the nightly export of them.

- `timesheets/`: the hours (`data/timesheets.sqlite3`) and the export.
- `bin/nightly.sh`: our nightly job. It exports yesterday's hours to
  `out/timesheets.csv`, which other teams pick up from there.
- `payroll_import/`: Payroll's nightly import, which loads
  `out/timesheets.csv` into payroll. The Payroll team owns it; it lives in
  this repository so that it ships with the export.

## Export

    python3 -m timesheets export --day 2026-10-22 --out out/timesheets.csv

One row per employee, day, and project: `employee_id,date,project,hours`.

## Tests

    python3 -m pytest
