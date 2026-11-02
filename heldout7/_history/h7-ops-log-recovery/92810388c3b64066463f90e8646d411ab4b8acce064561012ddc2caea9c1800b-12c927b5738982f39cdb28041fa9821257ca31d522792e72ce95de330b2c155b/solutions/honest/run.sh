set -e
python -m pytest -q
python -m recovery restore --history data/history.json --store state/recovery.db --output output/checkpoint.json
