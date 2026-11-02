from coordinator.auth import authorized, in_window
from coordinator.errors import CoordinatorError
from coordinator.loader import current_grants, current_operations
from coordinator.store import ResourceStore


def submission_ticks(bundle, operations, grants):
    """Ticks at which each member may be submitted (authorization, own window, batch window)."""
    batch = bundle['batch']
    ticks = {}
    for member, envelope in operations.items():
        ticks[member] = [t for t in range(batch['start_tick'], batch['end_tick'] + 1)
                         if in_window(envelope['signed'], t) and authorized(envelope, grants, bundle['keys'], t)]
    return ticks


def plan(bundle):
    """Exact search over (committed members, register values), keeping the earliest tick per state.

    Waiting is always allowed, so reaching a state earlier never removes options. Returns the
    commit order with ticks, or raises CoordinatorError describing how far the batch can get.
    """
    operations = current_operations(bundle)
    ticks = submission_ticks(bundle, operations, current_grants(bundle))
    names = sorted(operations)
    registers = sorted(bundle['initial'])
    start = (frozenset(), tuple(bundle['initial'][r] for r in registers))
    best = {start: (bundle['batch']['start_tick'] - 1, ())}
    layer = [start]
    for _ in names:
        following = []
        for state in layer:
            done, values = state
            tick, path = best[state]
            current = dict(zip(registers, values))
            for name in names:
                body = operations[name]['signed']
                later = [t for t in ticks[name] if t > tick]
                if name in done or not later or any(current[r] != v for r, v in body['expected'].items()):
                    continue
                updated = dict(current, **body['writes'])
                nxt = (done | {name}, tuple(updated[r] for r in registers))
                if nxt not in best or later[0] < best[nxt][0]:
                    if nxt not in best:
                        following.append(nxt)
                    best[nxt] = (later[0], path + ((later[0], name),))
        if not following:
            break
        layer = following
    complete = [best[s][1] for s in layer if len(s[0]) == len(names)]
    if complete:
        return list(complete[0])
    reached = set().union(*(state[0] for state in best))
    never = sorted(set(names) - reached)
    most = max(len(state[0]) for state in best)
    raise CoordinatorError(f'no order commits every member: at most {most} of {len(names)} can commit; '
                           f'never passes its checks in any permitted order: {", ".join(never) or "none individually"}')


def schedule(bundle):
    """Execute the planned order against the store; a failed check is recorded as a retry."""
    operations = current_operations(bundle)
    grants = current_grants(bundle)
    store = ResourceStore(bundle['initial'])
    attempts = []
    for tick, member in plan(bundle):
        envelope = operations[member]
        body = envelope['signed']
        if not (in_window(body, tick) and authorized(envelope, grants, bundle['keys'], tick)):
            raise CoordinatorError(f'{member} is not permitted at tick {tick}')
        result = 'committed' if store.compare_and_set(body['expected'], body['writes']) else 'retry'
        attempts.append({'tick': tick, 'operation': member, 'revision': body['revision'], 'result': result})
        if result != 'committed':
            raise CoordinatorError(f'{member} unexpectedly failed its check at tick {tick}')
    return attempts, store.snapshot()
