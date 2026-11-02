"""Primary author proof: stable-state search with expanded copy states (reference algorithm
from h6-ops-quorum-cut honest planner), plus a closed-component cut analysis."""
import copy, json
from collections import Counter, deque
from pathlib import Path
TASK = Path(__file__).resolve().parent.parent

def edges_of(d):
    latest = {}
    for r in d['links']:
        if r['id'] not in latest or r['revision'] > latest[r['id']]['revision']: latest[r['id']] = r
    return {(r['source'], r['target']) for r in latest.values() if r['enabled'] and r['valid_from'] <= d['at'] < r['valid_to']}

def safe(d, pos, shadow=None):
    usage = {r: 0 for r in d['rack_capacity']}
    if len(set(pos.values())) != len(pos): return False
    for u, n in pos.items():
        if d['units'][u]['size'] > d['nodes'][n]['capacity']: return False
        usage[d['nodes'][n]['rack']] += d['units'][u]['size']
    if shadow:
        u, n = shadow
        if n in pos.values() or d['units'][u]['size'] > d['nodes'][n]['capacity']: return False
        usage[d['nodes'][n]['rack']] += d['units'][u]['size']
    for g, p in d['groups'].items():
        nodes = [n for u, n in pos.items() if d['units'][u]['group'] == g]
        if len(nodes) < p['quorum'] or len({d['nodes'][n]['zone'] for n in nodes}) < p['min_zones']: return False
    return all(usage[r] <= v for r, v in d['rack_capacity'].items())

def explore(d, edges):
    units = sorted(d['units']); start = (tuple(d['initial']['positions'][u] for u in units), tuple(d['initial']['images'][u] for u in units))
    seen = {start: []}; queue = deque([start]); full = 0; transient_blocked = Counter(); commit_blocked = 0
    while queue:
        positions, images = state = queue.popleft(); pos = dict(zip(units, positions))
        for i, u in enumerate(units):
            for dest in sorted(d['nodes']):
                if dest in positions or (positions[i], dest) not in edges: continue
                moved = dict(pos, **{u: dest})
                if not safe(d, pos, (u, dest)):
                    if safe(d, moved): transient_blocked[f'{u}:{positions[i]}->{dest}'] += 1
                    continue
                full += 2
                if not safe(d, moved): commit_blocked += 1; continue
                p = list(positions); p[i] = dest; im = list(images); im[i] = 'new'; nxt = (tuple(p), tuple(im))
                if nxt not in seen: seen[nxt] = seen[state] + [['start', u, dest], ['ready', u, dest], ['commit', u, dest]]; queue.append(nxt)
    target = tuple(d['target'][u] for u in units); goal = seen.get((target, ('new',) * len(units)))
    return {'stable_states': len(seen), 'full_states': len(seen) + full, 'distinct_positions': len({s[0] for s in seen}),
            'target_positions_reached_any_image': any(s[0] == target for s in seen),
            'plan_actions': None if goal is None else len(goal), 'plan': goal,
            'transient_capacity_blocked_moves': dict(sorted(transient_blocked.items())), 'ready_copies_without_legal_commit': commit_blocked}

base = json.loads((TASK / 'workspace/data/fleet.json').read_text()); edges = edges_of(base)
result = {'active_links': sorted(map(list, edges)), 'current': explore(base, edges)}
result['current'].pop('plan')
variants = {}
for name in ['approved_relay_03', 'approved_return_30', 'approved_transfer_24', 'raised_east_rack', 'direct_heavy_15', 'small_swap_relay', 'small_swap_no_staging_room', 'reordered_relay_03']:
    d = json.loads((TASK / 'grader/cases' / (name + '.json')).read_text()); r = explore(d, edges_of(d))
    variants[name] = {'plan_actions': r['plan_actions'], 'full_states': r['full_states'], 'stable_states': r['stable_states']}
result['variants'] = variants
stale = copy.deepcopy(base); stale['links'] = [l for l in stale['links'] if not (l['id'] == 'regional-relay' and l['revision'] == 2)]
result['shortcut_superseded_regional_route_plan_actions'] = explore(stale, edges_of(stale))['plan_actions']
def explore_no_shadow(d, edges):
    global safe
    original = safe
    safe = lambda d, pos, shadow=None: original(d, pos)
    try: return explore(d, edges)['plan_actions']
    finally: safe = original
result['shortcut_ignore_staged_copy_size'] = explore_no_shadow(base, edges)
Path(__file__).with_name('proof_result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps(result, sort_keys=True))
assert result['current']['plan_actions'] is None and result['current']['full_states'] == 1473 and result['current']['stable_states'] == 269
assert variants['approved_relay_03']['plan_actions'] == 45
