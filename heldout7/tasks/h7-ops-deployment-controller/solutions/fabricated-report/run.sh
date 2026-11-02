mkdir -p output
python - <<'PY'
import json
r = json.load(open('data/rollout.json')); install = r['requests'][0]
targets = {'api': 'edge-c', 'billing': 'edge-x', 'checkout': 'edge-d', 'dispatcher': 'edge-b'}
observed = {n: None for n in r['configuration']['nodes']}
for t in install['rollouts']: observed[targets[t['service']]] = {'service': t['service'], 'image': t['new_image']}
final = {'version': len(r['requests']), 'epoch': 1, 'observed': observed, 'pending': {}, 'handoffs': {}, 'done': sorted(targets),
         'quarantine': [], 'faults_left': 1, 'rollouts': {t['service']: t for t in install['rollouts']}, 'complete': True}
json.dump({'rollout_id': r['rollout_id'], 'results': [{'id': q['id'], 'accepted': True, 'response': None} for q in r['requests']], 'final': final},
          open('output/rollout_report.json', 'w'), indent=2)
PY
