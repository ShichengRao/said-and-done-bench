"""Release policy selection: one eligible package per baseline world."""
from .packages import answer


def ambiguous(worlds, protected_mask):
    """True when the worlds contain both values of every protected bit."""
    if not worlds:
        return False
    union = common = worlds[0]
    for world in worlds[1:]:
        union |= world
        common &= world
    return (union ^ common) & protected_mask == protected_mask


def select(worlds, packages, protected_mask):
    """Package index per world, or None when no safe assignment exists.

    Each world takes its highest-utility package (ties by ID) whose count leaves the
    protected bits ambiguous among the baseline worlds giving that count.
    """
    table = []
    for world in worlds:
        options = [k for k, package in enumerate(packages)
                   if ambiguous([w for w in worlds if answer(package, w) == answer(package, world)], protected_mask)]
        if not options:
            return None
        table.append(min(options, key=lambda k: (-packages[k]['utility'], packages[k]['id'])))
    return tuple(table)
