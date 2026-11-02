"""Delivery timeline assembly from the service exports.

Service clocks are independent, so logged_at cannot order events across
exports. Every interleaving that respects export order, signed attestations,
copy use and the recorded operation outcomes is a possible history.
"""
from .authority import AuthorityState, OutcomeMismatch
from .batch import events


def ordering_constraints(batch):
    before = {event['id']: set() for event in events(batch)}
    for attestation in batch['ordering']:
        before[attestation['later']].add(attestation['earlier'])
    for event in events(batch):
        if event['kind'] == 'copy' and event['source']['kind'] == 'copy':
            before[event['id']].add(event['source']['id'])
        if event['kind'] == 'receipt':
            before[event['id']].add(event['copy'])
    return before


def consistent_histories(batch):
    """Yield (order, deliveries) for every history consistent with the batch evidence."""
    streams = [export['events'] for export in batch['exports']]
    before = ordering_constraints(batch)
    total = sum(len(stream) for stream in streams)

    def visit(positions, state, order, deliveries):
        if len(order) == total:
            yield list(order), list(deliveries)
            return
        done = set(order)
        for index, stream in enumerate(streams):
            if positions[index] == len(stream):
                continue
            event = stream[positions[index]]
            if not before[event['id']] <= done:
                continue
            following = state.clone()
            try:
                entry = following.apply(event)
            except OutcomeMismatch:
                continue
            advanced = list(positions)
            advanced[index] += 1
            yield from visit(advanced, following, order + [event['id']],
                             deliveries + ([entry] if entry is not None else []))

    yield from visit([0] * len(streams), AuthorityState(batch['records'], batch['credentials']), [], [])


def merge_exports(batch):
    """Kept for diagnostics only: logged_at order is not evidence across services."""
    return sorted(events(batch), key=lambda event: event['logged_at'])
