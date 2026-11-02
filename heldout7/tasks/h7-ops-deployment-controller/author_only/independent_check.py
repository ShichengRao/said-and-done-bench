"""Independent author check: validate the trusted grader oracle (reference controller logic) against the
h6 literal order/route oracle (author_only/literal_oracle.py: permutation x route enumeration, no recursive
adversarial solver). For the customer rollout and every grader case: each dispatch must equal the literal
lexical expectation, every reachable state must keep all allowed pending outcomes winning, safety invariants
must hold, and installs are accepted exactly when the literal oracle finds a robust plan."""
import copy, importlib.util, json
from pathlib import Path
TASK = Path(__file__).resolve().parent.parent
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
oracle = load('oracle', TASK / 'grader/oracle.py'); lit = load('literal', Path(__file__).with_name('literal_oracle.py'))

def check_safe(state, cfg):
    present = [v for v in state['observed'].values() if v]
    reserves = [a['target'] for a in state['pending'].values() if a['op'] == 'start']
    assert len(reserves) == len(set(reserves)) and len(present) + len(reserves) <= cfg['capacity']
    assert all(state['observed'][n] is None for n in reserves + state['quarantine'])
    assert len(state['pending']) <= cfg['max_handoffs'] and len(state['handoffs']) <= cfg['max_handoffs']
    if state['rollouts'] is not None:
        assert set(v['service'] for v in present) == set(state['rollouts'])
        assert lit.all_pending_outcomes_win(state, state['handoffs'], cfg)

def replay(cfg, requests):
    c = oracle.Controller(copy.deepcopy(cfg)); attempts = {}; stats = {'dispatches': 0, 'installs': 0, 'rejected': 0}
    for q in requests:
        before = oracle.semantic(c.inspect())
        if q['kind'] == 'install' and q['id'] not in c.state['requests']:
            tickets = {t['service']: t for t in q['rollouts']}
            winnable = len(tickets) == len(q['rollouts']) and all(set(t['targets']) <= set(cfg['nodes']) and t['source'] not in t['targets'] for t in q['rollouts']) and \
                lit.winning({s: dict(t, targets=sorted(t['targets'])) for s, t in tickets.items()}, {s: t['source'] for s, t in tickets.items()}, set(), set(), cfg['nodes'], cfg['capacity'], q['fault_budget'])
        try:
            out = c.apply(q)
        except ValueError:
            stats['rejected'] += 1; assert oracle.semantic(c.inspect()) == before; continue
        state = oracle.semantic(out)
        if q['kind'] == 'install' and before['version'] < state['version']:
            stats['installs'] += 1; attempts = {}
            if q['rollouts'] and not winnable: raise AssertionError('accepted an install the literal oracle cannot complete')
        if q['kind'] == 'dispatch' and before['version'] < state['version']:
            expected, pending, handoffs = lit.dispatch_expectation(before, cfg, attempts)
            assert out['created'] == expected and state['pending'] == pending and state['handoffs'] == handoffs, q['id']
            for token in expected:
                if pending[token]['op'] == 'start': attempts[pending[token]['service']] = pending[token]['attempt']
            stats['dispatches'] += 1
        check_safe(state, cfg)
    return c, stats

result = {}
rollout = json.loads((TASK / 'workspace/data/rollout.json').read_text()); cfg = rollout['configuration']; install = rollout['requests'][0]
tickets = {t['service']: dict(t, targets=sorted(t['targets'])) for t in install['rollouts']}; loc = {s: t['source'] for s, t in tickets.items()}
paths = lit.schedules(tickets, loc, set(), set(), cfg['nodes'], cfg['capacity']); robust = lit.robust_spines(tickets, loc, set(), set(), cfg['nodes'], cfg['capacity'], 1)
assert len(paths) == 44 and len(robust) == 10 and {p[0] for p in robust} == {('billing', 'edge-x'), ('checkout', 'edge-y')}
c, stats = replay(cfg, rollout['requests']); final = c.inspect()
assert final['complete'] and final['version'] == 21 and final['quarantine'] == ['edge-y']
result['customer'] = {'nominal_schedules': len(paths), 'robust_spines': len(robust), 'robust_first_moves': sorted(map(list, {p[0] for p in robust})),
                      'final_version': final['version'], 'placement': {v['service']: n for n, v in final['observed'].items() if v}, **stats}
for path in sorted((TASK / 'grader/cases').glob('*.json')):
    case = json.loads(path.read_text()); _, stats = replay(case['configuration'], [s for s in case['steps'] if s != 'inspect'])
    result[path.stem] = stats
Path(__file__).with_name('independent_result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps(result['customer']))
