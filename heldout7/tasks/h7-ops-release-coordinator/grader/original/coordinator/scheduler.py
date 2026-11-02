from coordinator.auth import authorized, in_window
from coordinator.errors import CoordinatorError
from coordinator.loader import current_grants, current_operations
from coordinator.store import ResourceStore


def schedule(bundle):
    """Submit each member in batch order and return the attempt log and final store values."""
    batch = bundle['batch']
    operations = current_operations(bundle)
    grants = current_grants(bundle)
    store = ResourceStore(bundle['initial'])
    attempts = []
    tick = batch['start_tick'] - 1
    for member in batch['members']:
        envelope = operations[member]
        body = envelope['signed']
        tick = max(tick + 1, body['window']['not_before'])
        if tick > batch['end_tick'] or not in_window(body, tick):
            raise CoordinatorError(f'{member} cannot be submitted inside its window')
        if not authorized(envelope, grants, bundle['keys'], tick):
            raise CoordinatorError(f'{member} is not authorized at tick {tick}')
        if not store.compare_and_set(body['expected'], body['writes']):
            raise CoordinatorError(f'{member} failed its expected-value check at tick {tick}')
        attempts.append({'tick': tick, 'operation': member, 'revision': body['revision'], 'result': 'committed'})
    return attempts, store.snapshot()
