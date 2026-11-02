"""Completion planner."""
from functools import lru_cache


def winning(state, locations, completed, quarantine, budget):
    services = tuple(sorted(state['rollouts']))
    routes = tuple(tuple(state['rollouts'][service]['targets']) for service in services)
    nodes = tuple(state['configuration']['nodes'])
    initial = tuple(locations[service] for service in services)
    finished = sum(1 << i for i, service in enumerate(services) if service in completed)
    enough_surge = state['configuration']['capacity'] > len(services)

    @lru_cache(None)
    def visit(position, done, bad, left):
        if done == (1 << len(services)) - 1:
            return True
        if not enough_surge:
            return False
        free = set(nodes) - set(position) - set(bad)
        for i, targets in enumerate(routes):
            if done & (1 << i):
                continue
            for target in targets:
                if target not in free:
                    continue
                after = list(position)
                after[i] = target
                if not visit(tuple(after), done | (1 << i), bad, left):
                    continue
                # TODO: account for the fault budget (`left`).
                return True
        return False

    return visit(initial, finished, tuple(sorted(quarantine)), budget)


def completion_preserved(state, handoffs):
    """True when the rollout can still finish once the given handoffs complete."""
    locations = dict(state['locations']); completed = set(state['done'])
    for service, handoff in handoffs.items():
        locations[service] = handoff['target']; completed.add(service)
    return winning(state, locations, completed, set(state['quarantine']), state['faults_left'])
