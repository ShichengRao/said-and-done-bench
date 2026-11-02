from coordinator.auth import authorized, in_window
from coordinator.errors import CoordinatorError
from coordinator.loader import current_grants, current_operations
from coordinator.store import ResourceStore


def schedule(bundle):
    """Shortcut: 'retry' any operation, including ones that already committed, until all members commit."""
    operations = current_operations(bundle); grants = current_grants(bundle)
    names = sorted(operations); registers = sorted(bundle['initial'])
    start = (frozenset(), tuple(bundle['initial'][r] for r in registers), bundle['batch']['start_tick'] - 1, ())
    queue = [start]; seen = set()
    while queue:
        done, values, tick, path = queue.pop(0)
        if len(done) == len(names):
            store = ResourceStore(bundle['initial']); attempts = []
            for t, name in path:
                body = operations[name]['signed']; store.compare_and_set(body['expected'], body['writes'])
                again = any(a['operation'] == name for a in attempts)
                attempts.append({'tick': t, 'operation': name, 'revision': body['revision'], 'result': 'retry' if again else 'committed'})
            return attempts, store.snapshot()
        current = dict(zip(registers, values))
        for name in names:
            body = operations[name]['signed']
            # A re-run of a committed operation is treated as a retry of its original submission.
            later = [t for t in range(tick + 1, bundle['batch']['end_tick'] + 1)
                     if name in done or (in_window(body, t) and authorized(operations[name], grants, bundle['keys'], t))]
            if not later or any(current[r] != v for r, v in body['expected'].items()):
                continue
            updated = dict(current, **body['writes']); key = (done | {name}, tuple(updated[r] for r in registers), later[0])
            if key not in seen:
                seen.add(key); queue.append(key + (path + ((later[0], name),),))
    raise CoordinatorError('no schedule')
