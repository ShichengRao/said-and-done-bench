"""The build order (see the README for its rules)."""

import heapq

from buildgraph.errors import CycleError, UnknownDependency, UnknownPackage


def _wanted(packages, targets):
    """The targets and everything they depend on (every package without targets)."""
    if targets is None:
        start = sorted(packages)
    else:
        start = list(targets)
        for target in start:
            if target not in packages:
                raise UnknownPackage(f'no package named {target}')
    wanted, stack = set(), start[::-1]
    while stack:
        name = stack.pop()
        if name in wanted:
            continue
        wanted.add(name)
        for dep in packages[name].deps:
            if dep not in packages:
                raise UnknownDependency(f'{name} depends on {dep}, which is not a package')
            stack.append(dep)
    return wanted


def _cycle(packages, stuck):
    """A dependency cycle among the packages that never became ready, from its first name back to it."""
    def back_to(start, name, path, seen):
        for dep in sorted(set(packages[name].deps) & stuck):
            if dep == start:
                return path + [start]
            if dep not in seen:
                seen.add(dep)
                found = back_to(start, dep, path + [dep], seen)
                if found:
                    return found
        return None

    for start in sorted(stuck):
        found = back_to(start, start, [start], set())
        if found:
            return found
    raise AssertionError('packages left over without a cycle')


def build_order(packages, targets=None):
    """The names of the packages to build, in order.

    packages is {name: Package}; with targets, only those and what they
    depend on are built.
    """
    wanted = _wanted(packages, targets)
    waiting = {name: set(packages[name].deps) for name in wanted}
    dependents = {name: [] for name in wanted}
    for name in wanted:
        for dep in waiting[name]:
            dependents[dep].append(name)
    ready = [name for name in wanted if not waiting[name]]
    heapq.heapify(ready)
    order = []
    while ready:
        name = heapq.heappop(ready)
        order.append(name)
        for dependent in dependents[name]:
            waiting[dependent].discard(name)
            if not waiting[dependent]:
                heapq.heappush(ready, dependent)
    if len(order) < len(wanted):
        raise CycleError('dependency cycle: ' + ' -> '.join(_cycle(packages, wanted - set(order))))
    return order
