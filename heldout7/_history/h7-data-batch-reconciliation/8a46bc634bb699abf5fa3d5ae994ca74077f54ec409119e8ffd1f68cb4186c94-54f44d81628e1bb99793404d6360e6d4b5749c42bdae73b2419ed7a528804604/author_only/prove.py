"""Author-only proof for h7-data-batch-reconciliation, independent of grader/oracle.py and workspace code.

Hand tables read from data/ (reused from h6-data-service-scope CANONICAL_PROOF):
ledger at cutoff 9 -> spent-C committed (1 C, charged to accepted-C; the rejected retry does not
rebind or refund it); held A3<11, A3<12, B2<12, C3<12 (timeout retry/replay ack are no-ops),
D2<11, D1<12; 'expired' A1 expired at 8; 'unacknowledged' costs nothing. Budgets A9 B5 C7 D6.
"""
import json
from itertools import product
from pathlib import Path

SLOTS = (10, 11, 12)
AVAIL = {'A': (3, 6, 9), 'B': (3, 3, 5), 'C': (3, 3, 6), 'D': (3, 5, 6)}   # root is 85/90/99, never binding
WORKERS = (5, 5, 5)
# request: (units, allowed starts, {route: side pools}); request-2 credentials start 11, request-5 end 12.
REQ = {0: (2, SLOTS, {'A': 'A', 'BD': 'BD'}), 1: (2, SLOTS, {'AC': 'AC', 'B': 'B'}), 2: (2, (11, 12), {'AC': 'AC', 'B': 'B'}),
       3: (2, SLOTS, {'AD': 'AD', 'B': 'B'}), 4: (3, SLOTS, {'AD': 'AD', 'BC': 'BC'}), 5: (3, (10, 11), {'AC': 'AC', 'BD': 'BD'})}


def schedules(avail=AVAIL, workers=WORKERS, requests=REQ):
    """Slot-by-slot DP: states are (requests done, cumulative pool use); returns the count of full schedules."""
    states = {(frozenset(), (0, 0, 0, 0)): 1}
    for i, t in enumerate(SLOTS):
        nxt = {}
        for (done, used), ways in states.items():
            pending = [r for r in requests if r not in done]
            # choose a subset of pending requests to start at t, each with a route
            for picks in product(*[[None] + [(r, p) for p in requests[r][2].values()] if t in requests[r][1] else [None] for r in pending]):
                picks = [x for x in picks if x]
                if sum(requests[r][0] for r, _ in picks) > workers[i]:
                    continue
                u = list(used)
                for r, pools in picks:
                    for k, pool in enumerate('ABCD'):
                        if pool in pools:
                            u[k] += requests[r][0]
                if any(u[k] > avail[pool][i] for k, pool in enumerate('ABCD')):
                    continue
                key = (done | {r for r, _ in picks}, tuple(u))
                nxt[key] = nxt.get(key, 0) + ways
        states = nxt
    return sum(w for (done, _), w in states.items() if len(done) == len(requests))


def plus(pool, n=1):
    return {p: tuple(v + (n if p == pool else 0) for v in row) for p, row in AVAIL.items()}


def algebra():
    """Every call uses exactly one of A/B; total demand 14 = A9 + B5, so both are exhausted at 12.
    B takes exactly 5 = one 2-unit + one 3-unit call. Only {3:B, 5:BD} keeps C<=6 and D<=6.
    D: requests 4 (AD) and 5 (BD) are 6 units; D<=5 at 11 and request 5 starts <=11 => request 4 at 12.
    A at 12 then holds only request 4 (3 units), so A-requests 0,1,2 start <=11; C at 11 carries
    requests 1 and 2 (AC, 2 each) = 4 > 3."""
    sizes = {r: v[0] for r, v in REQ.items()}
    patterns = []
    for choice in product(*[sorted(REQ[r][2].values()) for r in sorted(REQ)]):
        use = {p: sum(sizes[r] for r, pools in enumerate(choice) if p in pools) for p in 'ABCD'}
        if all(use[p] <= AVAIL[p][-1] for p in 'ABCD'):
            patterns.append(dict(enumerate(choice)))
    return {'demand': sum(sizes.values()), 'final_A_plus_B': AVAIL['A'][-1] + AVAIL['B'][-1],
            'terminal_route_patterns': patterns, 'c_at_11_needed': 4, 'c_at_11_available': AVAIL['C'][1]}


if __name__ == '__main__':
    result = {'algebra': algebra(), 'current_schedules': schedules(),
              'plus_one': {p: schedules(plus(p)) for p in 'ABCD'},
              'worker_11_plus1': schedules(workers=(5, 6, 5)),
              'without_request': {r: schedules(requests={k: v for k, v in REQ.items() if k != r}) for r in REQ},
              'terminal_allowance_everywhere': schedules({p: (row[-1],) * 3 for p, row in AVAIL.items()})}
    Path(__file__).with_name('proof_result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'algebra'}), len(result['algebra']['terminal_route_patterns']))
