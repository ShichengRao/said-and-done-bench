"""The build order (see the README for its rules)."""

from buildgraph.errors import CycleError, UnknownDependency, UnknownPackage


def build_order(packages, targets=None):
    """The names of the packages to build, in order.

    packages is {name: Package}; with targets, only those and what they
    depend on are built.
    """
    for name in sorted(packages):
        for dep in packages[name].deps:
            if dep not in packages:
                raise UnknownDependency(f'{name} depends on {dep}, which is not a package')
    order, left = [], set(packages)
    while left:
        ready = sorted(name for name in left if all(dep in order for dep in packages[name].deps))
        if not ready:
            raise CycleError('dependency cycle: ' + ' -> '.join(sorted(left)))
        order.append(ready[0])
        left.remove(ready[0])
    if targets is None:
        return order
    wanted, stack = set(), list(targets)
    while stack:
        name = stack.pop()
        if name not in packages:
            raise UnknownPackage(f'no package named {name}')
        if name not in wanted:
            wanted.add(name)
            stack.extend(packages[name].deps)
    return [name for name in order if name in wanted]
