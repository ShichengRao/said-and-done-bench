set -e
python3 -m pytest -q
if python3 -m stewardship.migrate --data data --output output/assignments.json; then exit 1; fi
test ! -e output/assignments.json
