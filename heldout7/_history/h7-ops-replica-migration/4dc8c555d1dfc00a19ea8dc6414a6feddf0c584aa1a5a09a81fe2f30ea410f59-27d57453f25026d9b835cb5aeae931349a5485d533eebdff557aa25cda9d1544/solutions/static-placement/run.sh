mkdir -p output
python - <<'PY'
import json
fleet = json.load(open('data/fleet.json'))
json.dump({'fleet_id': fleet['fleet_id'], 'actions': [['commit', u, n] for u, n in sorted(fleet['target'].items())],
           'final_positions': fleet['target']}, open('output/migration_plan.json', 'w'), indent=2)
PY
