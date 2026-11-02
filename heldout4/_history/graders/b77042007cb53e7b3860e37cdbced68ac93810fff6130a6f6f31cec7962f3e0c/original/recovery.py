def restore(bundle, target_sequence):
    rows = dict(bundle['snapshot']['rows'])
    for events in bundle['segments'].values():
        for event in events:
            if event['after'] is None: rows.pop(event['key'], None)
            else: rows[event['key']] = event['after']
    return {'sequence': target_sequence, 'rows': rows, 'transactions': []}
