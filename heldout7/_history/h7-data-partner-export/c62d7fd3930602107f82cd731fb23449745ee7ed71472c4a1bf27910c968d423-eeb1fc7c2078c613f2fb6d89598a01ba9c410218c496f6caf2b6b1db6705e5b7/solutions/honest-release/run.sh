set -e
python3 -m pytest -q
python3 -m partner_export.release --data data --output output/release.json
