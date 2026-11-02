set -e
python -m pytest -q
python -m ticket_index.replay --data data --output output/index.json
