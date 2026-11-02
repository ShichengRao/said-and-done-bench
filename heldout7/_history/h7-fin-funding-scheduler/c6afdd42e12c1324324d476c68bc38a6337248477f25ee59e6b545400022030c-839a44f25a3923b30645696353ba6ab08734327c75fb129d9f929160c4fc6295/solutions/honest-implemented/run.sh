set -euo pipefail
python -m pytest -q
if python -m funding_scheduler schedule --data data --output output/funding_schedule.json; then exit 1; fi
test ! -e output/funding_schedule.json
