#!/bin/sh
# Our nightly job (cron, 01:30 UTC): export yesterday's hours to out/timesheets.csv.
set -e
cd "$(dirname "$0")/.."
python3 -m timesheets export --out out/timesheets.csv
