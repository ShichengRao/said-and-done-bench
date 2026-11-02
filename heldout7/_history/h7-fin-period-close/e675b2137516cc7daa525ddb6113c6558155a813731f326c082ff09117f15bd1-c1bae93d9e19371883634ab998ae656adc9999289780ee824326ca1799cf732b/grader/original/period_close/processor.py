from .errors import CloseError


def current_events(deliveries, as_of):
    seen = {}
    current = {}
    for row in deliveries:
        if row['known'] > as_of:
            continue
        identity = (row['kind'], row['id'], row['revision'])
        value = {k: v for k, v in row.items() if k != 'event_id'}
        if identity in seen and seen[identity] != value:
            raise CloseError('Conflicting processor revision')
        seen[identity] = value
        if row['final']:
            # The file reader supplies records in delivery order.
            current[(row['kind'], row['id'])] = value
    return current
