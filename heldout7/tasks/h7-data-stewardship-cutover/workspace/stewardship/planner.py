"""Steward assignment planning."""
from .groups import group_load, group_owners, merge_groups
from .ledger import latest


class PlanningError(Exception):
    """No assignment satisfies the rules."""


def assign_phase(groups, records, capacity):
    """Assign each group (largest load first) to the first qualified owner with room."""
    remaining = dict(capacity)
    result = {}
    for group_id in sorted(groups, key=lambda g: (-group_load(groups[g], records), g)):
        load = group_load(groups[group_id], records)
        for owner in group_owners(groups[group_id], records):
            if remaining.get(owner, 0) >= load:
                remaining[owner] -= load
                result[group_id] = owner
                break
        else:
            raise PlanningError('no qualified owner has room for %s' % group_id)
    return result


def plan(cutover, entries):
    records = latest(entries, 'record')
    capacity = {owner: value['units'] for owner, value in latest(entries, 'capacity').items()}
    groups = merge_groups(records, latest(entries, 'merge'))
    phases = [assign_phase(groups, records, capacity) for _ in cutover['phases']]
    return {
        'cutover': cutover['cutover'], 'customer': cutover['customer'], 'phases': list(cutover['phases']),
        'groups': [{'id': g, 'members': groups[g], 'owners': [phase[g] for phase in phases]} for g in sorted(groups)],
    }
