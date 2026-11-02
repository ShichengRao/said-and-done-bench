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
        key = (row['kind'], row['id'])
        if row['final'] and (key not in current or row['revision'] > current[key]['revision']):
            current[key] = value
    return current
