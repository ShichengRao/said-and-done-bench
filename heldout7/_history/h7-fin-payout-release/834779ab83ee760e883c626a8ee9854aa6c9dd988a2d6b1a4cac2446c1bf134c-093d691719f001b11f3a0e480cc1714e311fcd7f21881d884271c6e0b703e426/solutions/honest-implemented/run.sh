set -euo pipefail
python -m pytest -q
if python -m payout_release schedule --data data --output output/release_schedule.json; then exit 1; fi
test ! -e output/release_schedule.json
