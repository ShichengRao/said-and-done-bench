"""Trusted stewardship oracle: sorted-revision snapshots, graph components and
whole owner-matrix enumeration. Never imports candidate code."""
import copy
import json
from itertools import product
from pathlib import Path


def read_data(root):
    root = Path(root)
    return {'cutover': json.loads((root / 'cutover.json').read_text()),
            'entries': json.loads((root / 'ledger.json').read_text())['entries']}


def write_data(root, data):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    (root / 'cutover.json').write_text(json.dumps(data['cutover'], indent=2) + '\n')
    (root / 'ledger.json').write_text(json.dumps({'entries': data['entries']}, indent=2) + '\n')


def reconstruct(data):
    rows = data['entries']; cutoff = data['cutover']['approval_cutoff']; phases = len(data['cutover']['phases'])
    ids = [(r['kind'], r['entity'], r['revision']) for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate revision')

    def snapshot(kind, phase):
        result = {}
        for row in sorted((r for r in rows if r['kind'] == kind and r['approved'] and r['effective'] <= phase and r['recorded'] <= cutoff), key=lambda r: r['revision']):
            result[row['entity']] = row['value']
        return result
    names = sorted(snapshot('record', 0)); adj = {n: set() for n in names}
    for m in snapshot('merge', 0).values():
        if m['active']:
            adj[m['left']].add(m['right']); adj[m['right']].add(m['left'])
    unseen = set(names); parts = []
    while unseen:
        stack = [min(unseen)]; members = set()
        while stack:
            node = stack.pop()
            if node not in members:
                members.add(node); stack.extend(adj[node] - members)
        unseen -= members; parts.append(sorted(members))
    groups = []
    for members in sorted(parts):
        loads, allowed, handoffs = [], [], []
        for k in range(phases):
            state = snapshot('record', k); loads.append(sum(state[n]['units'] for n in members))
            pool = {o for n in members for o in state[n]['owners']}
            allowed.append(sorted(o for o in pool if all(o in state[n]['owners'] for n in members)))
            if k < phases - 1:
                for grant in snapshot('handoff', k).values():
                    if grant['record'] in members and grant['boundary'] == k and grant['active']:
                        handoffs.append([k, grant['from'], grant['to']])
        groups.append({'id': members[0], 'members': members, 'load': loads, 'allowed': allowed, 'handoffs': sorted(handoffs)})
    caps = [snapshot('capacity', k) for k in range(phases)]
    owners = sorted(set().union(*caps))
    capacity = {o: [caps[k][o]['units'] if o in caps[k] else 0 for k in range(phases)] for o in owners}
    return {'phases': phases, 'capacity': capacity, 'groups': groups}


def legal_paths(plan, group):
    owners = sorted(plan['capacity']); out = []
    for vector in product(owners, repeat=plan['phases']):
        if any(o not in group['allowed'][i] for i, o in enumerate(vector)):
            continue
        if any(vector[i] != vector[i + 1] and [i, vector[i], vector[i + 1]] not in group['handoffs'] for i in range(plan['phases'] - 1)):
            continue
        out.append(list(vector))
    return out


def all_assignments(data, limit=None):
    plan = reconstruct(data); groups = plan['groups']; owners = sorted(plan['capacity']); found = []
    for matrix in product(*(legal_paths(plan, g) for g in groups)):
        if all(sum(g['load'][k] for g, path in zip(groups, matrix) if path[k] == o) <= plan['capacity'][o][k]
               for k in range(plan['phases']) for o in owners):
            found.append({g['id']: path for g, path in zip(groups, matrix)})
            if limit and len(found) >= limit:
                break
    return found


def validate_assignments(output, data):
    plan = reconstruct(data); errors = []
    if not all_assignments(data, limit=1):
        return ['approved ledger admits no assignment satisfying the cutover rules']
    if not isinstance(output, dict):
        return ['assignments are not an object']
    cut = data['cutover']
    for key, value in (('cutover', cut['cutover']), ('customer', cut['customer']), ('phases', cut['phases'])):
        if output.get(key) != value:
            errors.append('incorrect ' + key)
    rows = output.get('groups')
    expected = [{'id': g['id'], 'members': g['members']} for g in plan['groups']]
    if not isinstance(rows, list) or [{'id': r.get('id'), 'members': r.get('members')} if isinstance(r, dict) else None for r in rows] != expected:
        return errors + ['groups do not match the merged identity groups']
    usage = {o: [0] * plan['phases'] for o in plan['capacity']}
    for g, row in zip(plan['groups'], rows):
        path = row.get('owners')
        if not isinstance(path, list) or len(path) != plan['phases']:
            errors.append('missing owners for ' + g['id']); continue
        if path not in legal_paths(plan, g):
            errors.append('unqualified owner or unapproved transfer for ' + g['id']); continue
        for k, o in enumerate(path):
            usage[o][k] += g['load'][k]
    for o, row in usage.items():
        for k, used in enumerate(row):
            if used > plan['capacity'][o][k]:
                errors.append('capacity exceeded for %s in phase %d' % (o, k))
    return sorted(set(errors))


def _entry(kind, entity, value, revision=1, recorded=9, effective=0):
    return {'kind': kind, 'entity': entity, 'revision': revision, 'recorded': recorded, 'effective': effective,
            'approved': True, 'value': value}


def variant(data, name):
    """Author-only nearby counterparts and negative variants (copies; never shipped as approvals)."""
    other = copy.deepcopy(data)
    if name == 'reapproval_in_baseline':        # customer accepts ledger sequence 12 into the approved baseline
        other['cutover']['approval_cutoff'] = 12
    elif name == 'accounts_boundary0_handoff':
        other['entries'].append(_entry('handoff', 'accounts-early-transfer', {'record': 'accounts', 'boundary': 0, 'from': 'alpha', 'to': 'beta', 'active': True}))
    elif name == 'alpha_phase1_capacity':
        other['entries'] += [_entry('capacity', 'alpha', {'units': 4}, revision=5, effective=1),
                             _entry('capacity', 'alpha', {'units': 3}, revision=6, effective=2)]
    elif name == 'without_current_grants':     # removing the active grants: still no assignment
        other['entries'] = [e for e in other['entries'] if e['entity'] not in ('accounts-window-transfer', 'tickets-early-transfer')]
    else:
        raise KeyError(name)
    return other


def rename_owners(data, mapping):
    text = json.dumps(data)
    for old, new in mapping.items():
        text = text.replace('"%s"' % old, '"%s"' % new)
    return json.loads(text)
