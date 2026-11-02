set -e
python3 -m pytest -q
if python3 -m rollout.deploy --config data --output output/deployment.json; then exit 1; fi
test ! -e output/deployment.json
