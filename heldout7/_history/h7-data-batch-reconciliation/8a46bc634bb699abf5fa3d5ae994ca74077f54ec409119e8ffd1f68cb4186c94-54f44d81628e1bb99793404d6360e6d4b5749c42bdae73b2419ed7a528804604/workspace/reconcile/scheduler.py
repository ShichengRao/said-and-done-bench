"""Assign each call a route and start within worker and allowance limits."""


class ScheduleError(Exception):
    """The batch cannot be scheduled under the supplied rules."""


def schedule(batch, options, available):
    """Prototype: take the first option that still fits for each request, in request-ID order."""
    remaining = {pool: dict(row) for pool, row in available.items()}
    workers = {str(t): batch['workers'][str(t)] for t in batch['slots']}
    units = {q['id']: q['units'] for q in batch['requests']}
    chosen = {}
    for request_id in sorted(options):
        need = units[request_id]
        for option in options[request_id]:
            later = [str(t) for t in batch['slots'] if t >= option['start']]
            if workers[str(option['start'])] < need:
                continue
            if any(remaining[p][t] < need for p in option['pools'] for t in later):
                continue
            workers[str(option['start'])] -= need
            for pool in option['pools']:
                for t in later:
                    remaining[pool][t] -= need
            chosen[request_id] = option
            break
        else:
            raise ScheduleError('no remaining route/start for %s' % request_id)
    return chosen
