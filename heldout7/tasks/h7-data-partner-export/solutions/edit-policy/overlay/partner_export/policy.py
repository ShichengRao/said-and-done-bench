"""Release policy selection: one eligible package per baseline world.

The package ID is observable, so safety is judged on the whole policy's output groups:
the worlds the policy maps to the same package and count tuple.
"""
from functools import lru_cache

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
    """Best-utility safe policy as a package index per world, or None.

    Every safe policy is a cover of the worlds by its output groups (each a subset of
    one package's equal-count group that stays ambiguous); conversely, merging safe
    cells with the same package and counts stays safe. Search covers of the remaining
    worlds, always placing the lowest remaining world first, maximizing total utility
    and then the smallest package-ID tuple (packages are sorted by ID).
    """
    count = len(worlds)
    safe = [False] * (1 << count)
    for mask in range(1, 1 << count):
        safe[mask] = ambiguous([w for i, w in enumerate(worlds) if mask >> i & 1], protected_mask)
    groups = []
    for package in packages:
        by_answer = {}
        for i, world in enumerate(worlds):
            by_answer[answer(package, world)] = by_answer.get(answer(package, world), 0) | 1 << i
        groups.append([by_answer[answer(package, world)] for world in worlds])

    @lru_cache(maxsize=None)
    def cover(remaining):
        if not remaining:
            return 0, (-1,) * count
        first = (remaining & -remaining).bit_length() - 1
        best = None
        for k, package in enumerate(packages):
            available = groups[k][first] & remaining
            subset = available
            while subset:
                if subset >> first & 1 and safe[subset]:
                    child = cover(remaining ^ subset)
                    if child is not None:
                        table = tuple(k if subset >> i & 1 else child[1][i] for i in range(count))
                        result = (child[0] + subset.bit_count() * package['utility'], table)
                        if best is None or result[0] > best[0] or (result[0] == best[0] and result[1] < best[1]):
                            best = result
                subset = (subset - 1) & available
        return best

    if not worlds:
        return None
    result = cover((1 << count) - 1)
    return None if result is None else result[1]
