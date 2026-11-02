"""Replay worker: executes a release schedule step by step (docs/replay_worker.md)."""
from .errors import ReplayError


class ReplayWorker:
    def __init__(self, accounts, authority):
        self.owners = authority['owners']
        self.payouts = {p['id']: p for p in authority['payouts']}
        self.bridges = {b['id']: b for b in authority['bridges']}
        self.balances = {a['id']: a['balance'] for a in accounts}
        self.dispatched = set(); self.received = set(); self.active = None

    def account(self, owner):
        return self.owners[owner]

    def apply(self, step):
        kind, _, identity = step.partition(':')
        if kind == 'dispatch':
            p = self.payouts.get(identity)
            if p is None or identity in self.dispatched:
                raise ReplayError('cannot dispatch ' + identity)
            source = self.account(p['source_owner'])
            if self.balances[source] < p['cents']:
                raise ReplayError('insufficient balance in %s to dispatch %s' % (source, identity))
            self.balances[source] -= p['cents']; self.dispatched.add(identity)
        elif kind == 'receipt':
            p = self.payouts.get(identity)
            if p is None or identity not in self.dispatched or identity in self.received:
                raise ReplayError('cannot post receipt for ' + identity)
            if not all(x in self.dispatched for x in p['receipt_after']):
                raise ReplayError('provider has not released receipt for ' + identity)
            self.balances[self.account(p['destination_owner'])] += p['cents']; self.received.add(identity)
        elif kind == 'draw':
            b = self.bridges.get(identity)
            if b is None or self.active is not None:
                raise ReplayError('cannot draw bridge ' + identity)
            if not all(x in self.received for x in b['activate_after']):
                raise ReplayError('bridge %s is not yet active' % identity)
            self.balances[self.account(b['owner'])] += b['cents']; self.active = identity
        elif kind == 'repay':
            b = self.bridges.get(identity)
            if b is None or self.active != identity:
                raise ReplayError('bridge %s is not drawn' % identity)
            account = self.account(b['owner'])
            if self.balances[account] < b['cents'] or not all(x in self.received for x in b['release_after']):
                raise ReplayError('cannot repay bridge ' + identity)
            self.balances[account] -= b['cents']; self.active = None
        else:
            raise ReplayError('unknown step ' + step)

    def summary(self):
        return {'settled': sorted(self.received), 'active_bridge': self.active, 'balances': dict(self.balances),
                'complete': self.received == set(self.payouts) and self.active is None}

    def replay(self, plan):
        for step in plan:
            self.apply(step)
        return self.summary()
