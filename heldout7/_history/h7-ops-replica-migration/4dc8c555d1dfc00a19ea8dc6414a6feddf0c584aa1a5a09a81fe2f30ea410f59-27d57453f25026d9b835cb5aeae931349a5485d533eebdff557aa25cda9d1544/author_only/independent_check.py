"""Independent author check using the grader's separately written full copy-state BFS
(copying/ready/commit as distinct queue states, grouped revision authority)."""
import importlib.util, json
from pathlib import Path
TASK = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('oracle', TASK / 'grader/oracle.py'); oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
result = {}
for path in [TASK / 'workspace/data/fleet.json'] + sorted((TASK / 'grader/cases').glob('*.json')):
    d = oracle.read_fleet(path); ok, plan, count = oracle.search(d)
    result[path.stem if path.parent.name == 'cases' else 'current'] = {'feasible': ok, 'actions': None if plan is None else len(plan), 'reachable_full_states': count,
        'plan_validates': None if plan is None else oracle.validate_plan({'fleet_id': d['fleet_id'], 'actions': plan, 'final_positions': d['target']}, d) == []}
Path(__file__).with_name('independent_result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps(result, sort_keys=True))
assert result['current'] == {'feasible': False, 'actions': None, 'reachable_full_states': 1473, 'plan_validates': None}
assert result['approved_relay_03']['feasible'] and result['approved_relay_03']['plan_validates']
