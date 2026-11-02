set -e
python -m pytest -q
python -m deployctl run --rollout data/rollout.json --store state/controller.db --report output/rollout_report.json
