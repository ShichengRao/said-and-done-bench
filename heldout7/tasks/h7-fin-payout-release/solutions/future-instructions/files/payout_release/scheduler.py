"""Release scheduler: finds the step sequence that releases the whole batch.

Breadth-first search over execution states (dispatched, received, active bridge).
Balances are derived from the state using ACTUAL receipts: a destination is only
credited when its receipt has posted. Ties are broken by the lexicographically
smallest step sequence, so plans are deterministic.
"""
from collections import deque
from .authority import resolve
from .errors import ReleaseError


def explore(batch):
    """Return (payouts, {state: shortest lexicographically-least plan}) for every reachable state."""
    authority = resolve(batch)
    owners = authority['owners']; payouts = authority['payouts']; bridges = {b['id']: b for b in authority['bridges']}
    opening = {a['id']: a['balance'] for a in batch['accounts']}

    def balances(state):
        dispatched, received, active = state
        cash = dict(opening)
        for p in payouts:
            if p['id'] in dispatched:
                cash[owners[p['source_owner']]] -= p['cents']
            if p['id'] in received:
                cash[owners[p['destination_owner']]] += p['cents']
        if active is not None:
            cash[owners[bridges[active]['owner']]] += bridges[active]['cents']
        return cash

    start = (frozenset(), frozenset(), None)
    paths = {start: []}; queue = deque([start])
    while queue:
        state = queue.popleft(); dispatched, received, active = state; cash = balances(state); moves = []
        for p in payouts:
            if p['id'] not in dispatched and cash[owners[p['source_owner']]] >= p['cents']:
                moves.append(('dispatch:' + p['id'], (dispatched | {p['id']}, received, active)))
            if p['id'] in dispatched and p['id'] not in received and all(x in dispatched for x in p['receipt_after']):
                moves.append(('receipt:' + p['id'], (dispatched, received | {p['id']}, active)))
        if active is None:
            for b in bridges.values():
                if all(x in received for x in b['activate_after']):
                    moves.append(('draw:' + b['id'], (dispatched, received, b['id'])))
        else:
            b = bridges[active]
            if cash[owners[b['owner']]] >= b['cents'] and all(x in received for x in b['release_after']):
                moves.append(('repay:' + active, (dispatched, received, None)))
        for step, nxt in sorted(moves):
            if nxt not in paths:
                paths[nxt] = paths[state] + [step]; queue.append(nxt)
    return payouts, paths


def plan_release(batch):
    payouts, paths = explore(batch)
    every = frozenset(p['id'] for p in payouts)
    complete = [plan for (dispatched, received, active), plan in paths.items() if received == every and active is None]
    if complete:
        return min(complete, key=lambda plan: (len(plan), plan))
    cents = {p['id']: p['cents'] for p in payouts}
    best = max(paths, key=lambda s: sum(cents[x] for x in s[1]))
    missing = sorted(every - best[1])
    raise ReleaseError('no schedule under the current signed instructions settles every payout with all bridges repaid; '
                       'at most %d of %d cents can settle (never settled: %s; %d reachable states)'
                       % (sum(cents[x] for x in best[1]), sum(cents.values()), ', '.join(missing),
                          len(paths)))
