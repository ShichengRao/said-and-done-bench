"""Decoder for small generation records."""
from itertools import combinations
from .catalog import active_fragments
from .field import dot, solutions

class RestoreError(ValueError):
    pass

def recover(request):
    rows = [(r['coefficients'], r['value']) for r in active_fragments(request)]
    budget = min(request['fault_budget'], len(rows))
    candidates = set()
    for omitted in combinations(range(len(rows)), budget):
        retained = [row for i, row in enumerate(rows) if i not in omitted]
        for value in solutions(retained, request['width']):
            if sum(dot(c, value) != v for c, v in rows) <= budget:
                candidates.add(value)
    if not candidates:
        raise RestoreError('the supplied records do not establish a unique generation')
    return min(candidates)
