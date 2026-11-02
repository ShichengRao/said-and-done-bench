"""Primary author proof: exact state search over the supplied batch and named variants."""
import copy, importlib.util, itertools, json, sys
from pathlib import Path
TASK = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('oracle', TASK / 'grader/oracle.py'); oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)

def reachable(bundle):
    ops, ticks = oracle.facts(bundle); names = sorted(ops); res = sorted(bundle['initial'])
    start = (frozenset(), tuple(bundle['initial'][r] for r in res)); best = {start: 0}; queue = [start]
    for state in queue:
        done, values = state; cur = dict(zip(res, values))
        for n in names:
            later = [t for t in ticks[n] if t > best[state]]
            if n in done or not later or any(cur[r] != v for r, v in ops[n]['expected'].items()): continue
            new = dict(cur); new.update(ops[n]['writes']); nxt = (done | {n}, tuple(new[r] for r in res))
            if nxt not in best or later[0] < best[nxt]: best[nxt] = later[0]; queue.append(nxt)
    return best

base = oracle.read_bundle(TASK / 'workspace/data')
states = reachable(base)
committable = sorted(set().union(*(s[0] for s in states)))
maximum = max(len(s[0]) for s in states)
result = {'feasible': oracle.search(base)[0], 'reachable_states': len(states), 'max_committed': maximum,
          'ever_committable': committable,
          'edge_cutover_never_committable': 'edge-cutover' not in committable,
          'cache3_states_with_maint1': sum(1 for (d, v) in states if dict(zip(sorted(base['initial']), v))['cache'] == 3 and dict(zip(sorted(base['initial']), v))['maint'] == 1)}
drop = {}
for member in base['batch']['members']:
    b = copy.deepcopy(base); b['batch']['members'].remove(member); drop[member] = oracle.search(b)[0]
result['drop_one_member_feasible'] = drop
cases = {}
for case in sorted((TASK / 'grader/cases').iterdir()):
    ok, schedule = oracle.search(oracle.read_bundle(case))
    cases[case.name] = {'feasible': ok, 'schedule': [[a['tick'], a['operation']] for a in schedule] if ok else None}
result['grader_cases'] = cases
stale = copy.deepcopy(base); stale['envelopes'] = [e for e in stale['envelopes'] if not (e['signed']['id'] == 'edge-cutover' and e['signed']['revision'] == 2)]
result['shortcut_superseded_edge_revision_feasible'] = oracle.search(stale)[0]
(Path(__file__).with_name('proof_result.json')).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'grader_cases'}, sort_keys=True))
assert not result['feasible'] and result['edge_cutover_never_committable'] and result['max_committed'] == 6
