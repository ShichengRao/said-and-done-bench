from coordinator.auth import authorized, in_window
from coordinator.loader import current_grants, current_operations
from coordinator.store import ResourceStore


def schedule(bundle):
    """Shortcut: greedy retries; publish whatever committed."""
    operations = current_operations(bundle); grants = current_grants(bundle)
    store = ResourceStore(bundle['initial']); attempts = []; pending = list(bundle['batch']['members'])
    for tick in range(bundle['batch']['start_tick'], bundle['batch']['end_tick'] + 1):
        for name in list(pending):
            envelope = operations[name]; body = envelope['signed']
            if in_window(body, tick) and authorized(envelope, grants, bundle['keys'], tick) and store.compare_and_set(body['expected'], body['writes']):
                attempts.append({'tick': tick, 'operation': name, 'revision': body['revision'], 'result': 'committed'})
                pending.remove(name); break
    return attempts, store.snapshot()
