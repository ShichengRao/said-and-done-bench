"""Assign each call a route and start within worker and allowance limits."""


class ScheduleError(Exception):
    """The batch cannot be scheduled under the supplied rules."""


def schedule(batch, options, available):
    """Least complete assignment by backtracking over (route, start) options in request-ID order.

    Allowance taken by a call at start t stays spent at every later start, so a choice
    is charged against t and all later supplied starts.
    """
    slots = sorted(batch['slots'])
    last = str(slots[-1])
    remaining = {pool: {t: row[last] for t in row} for pool, row in available.items()}  # quota is per batch period
    workers = {str(t): batch['workers'][str(t)] for t in slots}
    units = {q['id']: q['units'] for q in batch['requests']}
    order = sorted(options)
    chosen = {}

    def apply(option, need, sign):
        workers[str(option['start'])] -= sign * need
        for pool in option['pools']:
            for t in slots:
                if t >= option['start']:
                    remaining[pool][str(t)] -= sign * need

    def visit(index):
        if index == len(order):
            return True
        request_id = order[index]; need = units[request_id]
        for option in options[request_id]:
            later = [str(t) for t in slots if t >= option['start']]
            if workers[str(option['start'])] < need or any(remaining[p][t] < need for p in option['pools'] for t in later):
                continue
            apply(option, need, 1); chosen[request_id] = option
            if visit(index + 1):
                return True
            apply(option, need, -1); del chosen[request_id]
        return False

    if not visit(0):
        raise ScheduleError('no assignment of routes and starts fits the worker capacity and the current allowances '
                            'at every start for all %d requests' % len(order))
    return dict(chosen)
