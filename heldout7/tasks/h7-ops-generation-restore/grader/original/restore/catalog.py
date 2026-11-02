"""Read the delivered fragment catalogue without changing source records."""
import hashlib
import json

def checksum(coefficients, value):
    body = json.dumps({'coefficients': coefficients, 'value': value}, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(body).hexdigest()

def active_fragments(request):
    revisions = {}; latest = {}
    for row in request['fragments']:
        key = (row['id'], row['revision'])
        if key in revisions and revisions[key] != row: raise ValueError('conflicting catalogue revision')
        revisions[key] = row
        if row['id'] not in latest or row['revision'] > latest[row['id']]['revision']:
            latest[row['id']] = row
    return [row for _, row in sorted(latest.items())
            if row['live'] and (row['tenant'], row['generation']) == (request['tenant'], request['generation'])
            and checksum(row['coefficients'], row['value']) == row['sha256']]
