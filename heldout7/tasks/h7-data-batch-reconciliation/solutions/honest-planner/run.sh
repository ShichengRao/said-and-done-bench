set -e
python3 -m pytest -q
if python3 -m reconcile.runner --data data --output output/schedule.json; then exit 1; fi
test ! -e output/schedule.json
