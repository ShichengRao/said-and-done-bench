set -e
python -m pytest -q
if python -m migration plan --fleet data/fleet.json --output output/migration_plan.json; then exit 1; fi
test ! -e output/migration_plan.json
