from coordinator.auth import authorized, in_window
from coordinator.loader import current_grants, current_operations
from coordinator.store import ResourceStore


def schedule(bundle):
    """Shortcut: submit in filed order with retries, then force-apply anything still pending at the end."""
    operations = current_operations(bundle); grants = current_grants(bundle)
    store = ResourceStore(bundle['initial']); attempts = []; pending = list(bundle['batch']['members'])
    tick = bundle['batch']['start_tick']
    while pending and tick <= bundle['batch']['end_tick']:
        for name in list(pending):
            envelope = operations[name]; body = envelope['signed']
            if in_window(body, tick) and authorized(envelope, grants, bundle['keys'], tick) and store.compare_and_set(body['expected'], body['writes']):
                attempts.append({'tick': tick, 'operation': name, 'revision': body['revision'], 'result': 'committed'})
                pending.remove(name); break
        tick += 1
    values = store.snapshot()
    for name in pending:
        body = operations[name]['signed']; values.update(body['writes'])
        attempts.append({'tick': tick, 'operation': name, 'revision': body['revision'], 'result': 'committed'}); tick += 1
    return attempts, values
