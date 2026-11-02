"""Reservation ledger replay at the batch cutoff."""
from .records import collapse, credentials


def replay(batch, ledger):
    """Return {reservation: {key, attempt, units, pools, expires, state}} at batch['as_of']."""
    cutoff = batch['as_of']
    table = credentials(batch)
    attempts = collapse(ledger['attempts'], 'attempt')
    receipts = collapse(ledger['receipts'], 'receipt')
    for attempt in attempts.values():
        if any(name not in table for name in attempt['credentials']):
            raise ValueError('attempt %s names unknown credential' % attempt['id'])
    declared = {r['reservation'] for r in receipts.values() if r['kind'] == 'reserve'}
    for receipt in receipts.values():
        if receipt['kind'] in ('reserve', 'reject') and receipt['attempt'] not in attempts:
            raise ValueError('receipt %s names unknown attempt' % receipt['id'])
        if receipt['kind'] in ('commit', 'release') and receipt['reservation'] not in declared:
            raise ValueError('receipt %s names unknown reservation' % receipt['id'])
    reservations, keys = {}, {}
    for receipt in sorted(receipts.values(), key=lambda r: (r['at'], r['id'])):
        if receipt['at'] > cutoff:
            continue
        kind = receipt['kind']
        if kind in ('reserve', 'reject'):
            attempt = attempts[receipt['attempt']]
            if attempt['at'] > receipt['at']:
                raise ValueError('receipt %s precedes its attempt' % receipt['id'])
        if kind == 'reject':
            continue
        name = receipt['reservation']
        if kind == 'reserve':
            binding = {'key': attempt['key'], 'attempt': attempt['id'], 'units': attempt['units'],
                       'pools': sorted({table[c]['pool'] for c in attempt['credentials']}), 'expires': receipt['expires']}
            if name in reservations:
                if reservations[name]['binding'] != binding:
                    raise ValueError('reservation %s rebound' % name)
            else:
                if attempt['key'] in keys or receipt['expires'] <= receipt['at']:
                    raise ValueError('key reused or reservation %s acknowledged after expiry' % name)
                keys[attempt['key']] = name
                reservations[name] = {'binding': binding, 'state': 'held'}
            continue
        if name not in reservations:
            raise ValueError('terminal receipt %s before reserve' % receipt['id'])
        entry = reservations[name]
        target = 'committed' if kind == 'commit' else 'released'
        if entry['state'] not in ('held', target):
            raise ValueError('contradictory terminal receipts for %s' % name)
        if kind == 'commit' and entry['state'] == 'held' and receipt['at'] >= entry['binding']['expires']:
            raise ValueError('reservation %s committed at or after expiry' % name)
        entry['state'] = target
    for attempt in attempts.values():
        owner = keys.get(attempt['key'])
        if attempt['transport'] == 'timeout' and owner is not None and reservations[owner]['state'] == 'held' \
                and attempt['id'] != reservations[owner]['binding']['attempt'] and attempt['at'] <= cutoff:
            reservations[owner]['state'] = 'released'  # timed-out retry: client gave up the hold
    result = {}
    for name, entry in sorted(reservations.items()):
        state = entry['state']
        if state == 'held' and entry['binding']['expires'] <= cutoff:
            state = 'expired'
        result[name] = {**entry['binding'], 'state': state}
    return result


def availability(batch, reservations):
    """Remaining allowance per pool at each supplied start: {pool: {str(slot): units}}."""
    def charged(pool, slot):
        return sum(r['units'] for r in reservations.values() if pool in r['pools'] and
                   (r['state'] == 'committed' or r['state'] == 'held' and slot < r['expires']))
    return {pool: {str(t): batch['budgets'][pool] - charged(pool, t) for t in sorted(batch['slots'])}
            for pool in sorted(batch['budgets'])}
