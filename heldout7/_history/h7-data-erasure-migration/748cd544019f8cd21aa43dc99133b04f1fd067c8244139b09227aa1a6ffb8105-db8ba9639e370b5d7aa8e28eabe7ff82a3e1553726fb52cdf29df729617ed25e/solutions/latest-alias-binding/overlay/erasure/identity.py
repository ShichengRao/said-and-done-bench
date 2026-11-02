"""Historical identity resolution and directly erased payload rows."""


def requests_for(row, identity, requests, now=None):
    """Sorted IDs of requests that directly erase this payload row ([] for tombstones)."""
    if row['deleted']:
        return []
    subjects = {i['subject'] for i in identity if i['tenant'] == row['tenant'] and i['alias'] == row['alias']
                and i['from'] <= (row['at'] if now is None else now) and (i['until'] is None or (row['at'] if now is None else now) < i['until'])}
    if len(subjects) != 1:
        raise ValueError('row %s needs exactly one subject, found %d' % (row['key'], len(subjects)))
    subject = next(iter(subjects))
    return sorted(r['id'] for r in requests if r['tenant'] == row['tenant'] and r['subject'] == subject and row['at'] <= r['through'])


def erased_payloads(nodes, identity, requests, now=None):
    found = []
    for name in sorted(nodes):
        for row in nodes[name]['rows']:
            ids = requests_for(row, identity, requests, now)
            if ids:
                found.append({'node': name, 'key': row['key'], 'requests': ids})
    return sorted(found, key=lambda r: (r['node'], r['key']))
