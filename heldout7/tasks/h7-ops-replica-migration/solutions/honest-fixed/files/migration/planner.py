from collections import deque

from migration.errors import MigrationError
from migration.fleet import active_links
from migration.safety import final_placement_problems, violations


def _successors(fleet, links, units, nodes, state):
    positions, images, shadow = state
    if shadow is None:
        current = dict(zip(units, positions))
        for index, unit in enumerate(units):
            for node in nodes:
                if node in positions or (positions[index], node) not in links:
                    continue
                if not violations(fleet, current, [unit, node, 'copying']):
                    yield ['start', unit, node], (positions, images, (unit, node, 'copying'))
    elif shadow[2] == 'copying':
        yield ['ready', shadow[0], shadow[1]], (positions, images, (shadow[0], shadow[1], 'ready'))
    else:
        unit, node, _ = shadow
        index = units.index(unit)
        moved = list(positions); moved[index] = node
        if not violations(fleet, dict(zip(units, moved))):
            updated = list(images); updated[index] = 'new'
            yield ['commit', unit, node], (tuple(moved), tuple(updated), None)


def plan_migration(fleet):
    """Shortest action sequence to the exact target, found by breadth-first search over every
    controller state (active placement, images, and the staged copy with its phase)."""
    problems = final_placement_problems(fleet, fleet['target'])
    if problems:
        raise MigrationError('target placement is not acceptable: ' + '; '.join(problems))
    links = active_links(fleet)
    units = sorted(fleet['units']); nodes = sorted(fleet['nodes'])
    start = (tuple(fleet['initial']['positions'][u] for u in units), tuple(fleet['initial']['images'][u] for u in units), None)
    goal = (tuple(fleet['target'][u] for u in units), tuple('new' for _ in units), None)
    paths = {start: []}
    queue = deque([start])
    while queue:
        state = queue.popleft()
        if state == goal:
            return paths[state]
        for action, nxt in _successors(fleet, links, units, nodes, state):
            if nxt not in paths:
                paths[nxt] = paths[state] + [action]
                queue.append(nxt)
    placements = {s[0] for s in paths}
    raise MigrationError(f'target placement is unreachable under the current links and capacity rules: '
                         f'searched all {len(paths)} reachable controller states ({len(placements)} active placements)')
