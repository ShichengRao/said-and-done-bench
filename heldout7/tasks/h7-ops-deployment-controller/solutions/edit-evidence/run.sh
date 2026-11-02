python - <<'PY'
import json
r = json.load(open('data/rollout.json')); r['requests'] = [q for q in r['requests'] if q['id'] not in ('q7', 'q14')]
json.dump(r, open('data/rollout.json', 'w'), indent=1)
PY
python -m deployctl run --rollout data/rollout.json --store state/controller.db --report output/rollout_report.json
