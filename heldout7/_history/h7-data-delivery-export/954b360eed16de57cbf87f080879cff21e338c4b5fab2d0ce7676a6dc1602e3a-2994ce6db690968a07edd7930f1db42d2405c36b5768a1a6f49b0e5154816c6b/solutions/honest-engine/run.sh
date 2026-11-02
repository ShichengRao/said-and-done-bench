set -e
python3 -m pytest -q
if python3 -m delivery_export.cli --batch data --output output/certificate.json; then exit 1; fi
test ! -e output/certificate.json
