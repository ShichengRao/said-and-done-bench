set -euo pipefail
set +e
python -m payout_release schedule --data data --output output/release_schedule.json
status=$?
set -e
test "$status" -eq 2
test ! -e output/release_schedule.json
