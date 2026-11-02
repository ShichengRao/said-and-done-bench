"""Completion planner: existential controller choices against every allowed start outcome."""
import itertools
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
                if left == 0 or visit(position, done, tuple(sorted((*bad, target))), left - 1):
                    return True
        return False

    return visit(initial, finished, tuple(sorted(quarantine)), budget)


def completion_preserved(state, handoffs):
    unknown = sorted(service for service, h in handoffs.items() if h['phase'] == 'starting')
    maximum = len(unknown) if state['faults_left'] else 0
    for nfailed in range(min(len(unknown), maximum) + 1):
        for failed in itertools.combinations(unknown, nfailed):
            locations = dict(state['locations'])
            completed = set(state['done'])
            bad = set(state['quarantine'])
            for service, handoff in handoffs.items():
                if service in failed:
                    bad.add(handoff['target'])
                else:
                    locations[service] = handoff['target']
                    completed.add(service)
            remaining = max(0, state['faults_left'] - nfailed)
            if not winning(state, locations, completed, bad, remaining):
                return False
    return True
