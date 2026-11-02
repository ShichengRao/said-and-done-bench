set -e
python3 -m pytest -q
python3 -m checkpoint.publish --data data --output output/checkpoint.json
