"""Release scheduler: finds the step sequence that releases the whole batch.

TODO: bridges are not scheduled yet (draw/repay).
"""
from collections import deque
from .authority import resolve
from .errors import ReleaseError


def plan_release(batch):
    authority = resolve(batch)
    owners = authority['owners']; payouts = authority['payouts']
    opening = {a['id']: a['balance'] for a in batch['accounts']}
    every = frozenset(p['id'] for p in payouts)

    def balances(dispatched):
        cash = dict(opening)
        for p in payouts:
            if p['id'] in dispatched:
                cash[owners[p['source_owner']]] -= p['cents']
                cash[owners[p['destination_owner']]] += p['cents']
        return cash

    start = (frozenset(), frozenset())
    paths = {start: []}; queue = deque([start])
    while queue:
        state = queue.popleft(); dispatched, received = state
        if received == every:
            return paths[state]
        cash = balances(dispatched)
        moves = []
        for p in payouts:
            if p['id'] not in dispatched and cash[owners[p['source_owner']]] >= p['cents']:
                moves.append(('dispatch:' + p['id'], (dispatched | {p['id']}, received)))
            if p['id'] in dispatched and p['id'] not in received and all(x in dispatched for x in p['receipt_after']):
                moves.append(('receipt:' + p['id'], (dispatched, received | {p['id']})))
        for step, nxt in sorted(moves):
            if nxt not in paths:
                paths[nxt] = paths[state] + [step]; queue.append(nxt)
    raise ReleaseError('no schedule releases the whole batch')
