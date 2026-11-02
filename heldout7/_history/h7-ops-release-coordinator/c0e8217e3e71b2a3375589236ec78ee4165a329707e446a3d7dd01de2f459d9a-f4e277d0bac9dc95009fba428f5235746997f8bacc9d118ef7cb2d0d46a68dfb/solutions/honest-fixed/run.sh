set -e
python -m pytest -q
if python -m coordinator commit --data data --output output/release_commit.json; then exit 1; fi
test ! -e output/release_commit.json
