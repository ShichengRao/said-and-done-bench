"""Trusted migration oracle: grouped-revision link authority, independent full copy-state BFS
(copying, ready and commit states are separate queue entries) and an action replayer.
Never imports candidate code."""
import json
from collections import deque
from pathlib import Path


def read_fleet(path):
    return json.loads(Path(path).read_text())


def authority(d):
    result = set()
    for name in {r['id'] for r in d['links']}:
        rows = [r for r in d['links'] if r['id'] == name]
        for revision in {r['revision'] for r in rows}:
            same = [r for r in rows if r['revision'] == revision]
            if any(r != same[0] for r in same):
                raise ValueError('conflicting link revision')
        latest = max(rows, key=lambda r: r['revision'])
        if latest['enabled'] and latest['valid_from'] <= d['at'] < latest['valid_to']:
            result.add((latest['source'], latest['target']))
    return result


def _safe(d, pos, shadow):
    occupied = list(pos.values()) + ([] if shadow is None else [shadow[1]])
    if len(set(occupied)) != len(occupied):
        return False
    costs = {r: 0 for r in d['rack_capacity']}
    for unit, node in list(pos.items()) + ([] if shadow is None else [(shadow[0], shadow[1])]):
        size = d['units'][unit]['size']
        if size > d['nodes'][node]['capacity']:
            return False
        costs[d['nodes'][node]['rack']] += size
    for group, policy in d['groups'].items():
        places = [n for u, n in pos.items() if d['units'][u]['group'] == group]
        if len(places) < policy['quorum'] or len({d['nodes'][n]['zone'] for n in places}) < policy['min_zones']:
            return False
    return all(costs[r] <= v for r, v in d['rack_capacity'].items())


def final_valid(d):
    pos = d['target']
    return _safe(d, pos, None) and all(n in d['units'][u]['allowed_final'] for u, n in pos.items())


def step(d, edges, state, action):
    """Apply one action to (positions, images, shadow); return the new state or None if illegal."""
    pos, images, shadow = state
    if not (isinstance(action, list) and len(action) == 3):
        return None
    kind, unit, node = action
    if unit not in pos or node not in d['nodes']:
        return None
    if kind == 'start':
        new = [unit, node, 'copying']
        if shadow is None and (pos[unit], node) in edges and _safe(d, pos, new):
            return pos, images, new
    elif kind == 'ready':
        if shadow == [unit, node, 'copying']:
            return pos, images, [unit, node, 'ready']
    elif kind == 'commit':
        if shadow == [unit, node, 'ready']:
            moved = dict(pos, **{unit: node})
            if _safe(d, moved, None):
                return moved, dict(images, **{unit: 'new'}), None
    return None


def search(d):
    """Breadth-first search over every full state. Returns (feasible, shortest actions or None, reachable count)."""
    edges = authority(d); units = sorted(d['units']); nodes = sorted(d['nodes'])
    key = lambda s: (tuple(s[0][u] for u in units), tuple(s[1][u] for u in units), None if s[2] is None else tuple(s[2]))
    start = (dict(d['initial']['positions']), dict(d['initial']['images']), None)
    paths = {key(start): []}; queue = deque([start]); goal = None
    while queue:
        state = queue.popleft(); path = paths[key(state)]
        if goal is None and state[2] is None and state[0] == d['target'] and all(v == 'new' for v in state[1].values()) and final_valid(d):
            goal = path
        if state[2] is None:
            options = [['start', u, n] for u in units for n in nodes]
        else:
            options = [['ready', state[2][0], state[2][1]], ['commit', state[2][0], state[2][1]]]
        for action in options:
            nxt = step(d, edges, state, action)
            if nxt is not None and key(nxt) not in paths:
                paths[key(nxt)] = path + [action]; queue.append(nxt)
    return goal is not None, goal, len(paths)


def validate_plan(record, d):
    if not isinstance(record, dict):
        return ['migration plan is not an object']
    errors = []
    if record.get('fleet_id') != d['fleet_id']:
        errors.append('incorrect fleet_id')
    actions = record.get('actions')
    if not isinstance(actions, list):
        return errors + ['actions must be a list']
    try:
        edges = authority(d)
    except ValueError as error:
        return errors + [str(error)]
    state = (dict(d['initial']['positions']), dict(d['initial']['images']), None)
    for index, action in enumerate(actions):
        nxt = step(d, edges, state, action)
        if nxt is None:
            return errors + [f'action {index} {action!r} is not permitted']
        state = nxt
    if state[2] is not None or state[0] != d['target'] or any(v != 'new' for v in state[1].values()) or not final_valid(d):
        errors.append('sequence does not finish at the approved target placement')
    if record.get('final_positions') != state[0]:
        errors.append('final_positions differs from replay')
    return sorted(set(errors))
