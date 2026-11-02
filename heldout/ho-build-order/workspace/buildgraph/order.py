"""The build order (see the README for its rules)."""


def build_order(packages, targets=None):
    """The names of the packages to build, in order.

    packages is {name: Package}; with targets, only those and what they
    depend on are built.
    """
    order, done = [], set()

    def visit(name):
        if name in done:
            return
        done.add(name)
        for dep in packages[name].deps:
            visit(dep)
        order.append(name)

    for name in (targets or sorted(packages)):
        visit(name)
    return order
