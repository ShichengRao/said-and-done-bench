set +e
python -m deployctl run --rollout data/rollout.json --store state/controller.db --report output/rollout_report.json
status=$?
set -e
test "$status" -eq 2
test ! -e output/rollout_report.json
