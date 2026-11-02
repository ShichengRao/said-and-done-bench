set -e
python3 -m pytest -q
python3 -m erasure.migrate --data data --output output/migration.json
