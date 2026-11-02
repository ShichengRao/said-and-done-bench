"""Steward assignment planning across cutover phases with ownership continuity."""
from itertools import combinations, product

from .groups import group_load, group_owners, merge_groups
from .ledger import resolve


class PlanningError(Exception):
    """No assignment satisfies the rules."""


def build_model(cutover, entries):
    cutoff = cutover['approval_cutoff']
    phases = len(cutover['phases'])
    records = [resolve(entries, 'record', k, cutoff) for k in range(phases)]
    groups = merge_groups(records[0], resolve(entries, 'merge', 0, cutoff))
    capacity = {}
    for k in range(phases):
        for owner, value in resolve(entries, 'capacity', k, cutoff).items():
            capacity.setdefault(owner, [0] * phases)[k] = value['units']
    model = []
    for group_id in sorted(groups):
        members = groups[group_id]
        handoffs = set()
        for k in range(phases - 1):
            for grant in resolve(entries, 'handoff', k, cutoff).values():
                if grant['active'] and grant['boundary'] == k and grant['record'] in members:
                    handoffs.add((k, grant['from'], grant['to']))
        model.append({'id': group_id, 'members': members,
                      'load': [group_load(members, records[k]) for k in range(phases)],
                      'allowed': [group_owners(members, records[k]) for k in range(phases)],
                      'handoffs': handoffs})
    return {'phases': phases, 'capacity': capacity, 'groups': model}


def legal_paths(group, phases):
    paths = []
    for path in product(*group['allowed']):
        if all(a == b or any((x, a, b) in group['handoffs'] for x in range(phases)) for k, (a, b) in enumerate(zip(path, path[1:]))):
            paths.append(list(path))
    return paths


def search(model, groups):
    usage = {owner: [0] * model['phases'] for owner in model['capacity']}
    chosen = {}
    options = {g['id']: legal_paths(g, model['phases']) for g in groups}

    def visit(index):
        if index == len(groups):
            return dict(chosen)
        group = groups[index]
        for path in options[group['id']]:
            if any(usage.get(o, [0] * model['phases'])[k] + group['load'][k] > model['capacity'].get(o, [0] * model['phases'])[k]
                   for k, o in enumerate(path)):
                continue
            for k, o in enumerate(path):
                usage[o][k] += group['load'][k]
            chosen[group['id']] = path
            found = visit(index + 1)
            if found is not None:
                return found
            for k, o in enumerate(path):
                usage[o][k] -= group['load'][k]
            del chosen[group['id']]
        return None
    return visit(0)


def explain(model):
    groups = model['groups']
    for size in range(1, len(groups) + 1):
        for subset in combinations(groups, size):
            if search(model, list(subset)) is None:
                parts = ['%s paths %s loads %s' % (g['id'], [''.join(o[0] for o in p) for p in legal_paths(g, model['phases'])], g['load'])
                         for g in subset]
                return 'groups %s cannot be assigned together (%s; capacity %s)' % (
                    ', '.join(g['id'] for g in subset), '; '.join(parts), model['capacity'])
    return 'no assignment'


def plan(cutover, entries):
    model = build_model(cutover, entries)
    assignment = search(model, model['groups'])
    if assignment is None:
        raise PlanningError(explain(model))
    return {'cutover': cutover['cutover'], 'customer': cutover['customer'], 'phases': list(cutover['phases']),
            'groups': [{'id': g['id'], 'members': g['members'], 'owners': assignment[g['id']]} for g in model['groups']]}
