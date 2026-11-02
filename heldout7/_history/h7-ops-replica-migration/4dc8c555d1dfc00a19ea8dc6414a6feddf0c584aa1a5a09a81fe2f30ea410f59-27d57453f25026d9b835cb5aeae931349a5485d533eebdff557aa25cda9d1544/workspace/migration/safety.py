def violations(fleet, positions, shadow=None):
    """Safety problems for active placement `positions` plus an optional staged copy.

    `shadow` is None or [unit, node, phase]. A staged copy occupies its node and uses
    node and rack capacity like an active replica, but does not vote or count for zones.
    """
    problems = []
    occupied = list(positions.values()) + ([shadow[1]] if shadow else [])
    if len(set(occupied)) != len(occupied):
        problems.append('a node holds more than one copy')
    usage = {rack: 0 for rack in fleet['rack_capacity']}
    copies = list(positions.items()) + ([(shadow[0], shadow[1])] if shadow else [])
    for unit, node in copies:
        size = fleet['units'][unit]['size']
        if size > fleet['nodes'][node]['capacity']:
            problems.append(f'{unit} does not fit on {node}')
        usage[fleet['nodes'][node]['rack']] += size
    for rack, allowance in fleet['rack_capacity'].items():
        if usage[rack] > allowance:
            problems.append(f'rack {rack} uses {usage[rack]} of {allowance}')
    for group, policy in fleet['groups'].items():
        nodes = [node for unit, node in positions.items() if fleet['units'][unit]['group'] == group]
        if len(nodes) < policy['quorum']:
            problems.append(f'group {group} below quorum')
        if len({fleet['nodes'][n]['zone'] for n in nodes}) < policy['min_zones']:
            problems.append(f'group {group} below zone coverage')
    return problems


def final_placement_problems(fleet, positions):
    problems = violations(fleet, positions)
    for unit, node in positions.items():
        if node not in fleet['units'][unit]['allowed_final']:
            problems.append(f'{unit} is not approved to finish on {node}')
    return problems
