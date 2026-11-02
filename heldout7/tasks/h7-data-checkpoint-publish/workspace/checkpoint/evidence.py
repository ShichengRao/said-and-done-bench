"""Loading and validation of the exported shard logs."""
import json
from pathlib import Path

FILES = ('snapshot', 'request', 'transactions', 'deliveries')


def load(root):
    root = Path(root)
    return {name: json.loads((root / ('%s.json' % name)).read_text()) for name in FILES}


def manifest(export):
    table = {t['id']: t for t in export['transactions']}
    if len(table) != len(export['transactions']):
        raise ValueError('duplicate transaction ID')
    return table


def delivered(export, table):
    """{(shard, offset): row} after collapsing identical replays; rows must match the manifest."""
    logs = {}
    for row in export['deliveries']:
        key = (row['shard'], row['offset'])
        if key in logs and logs[key] != row:
            raise ValueError('conflicting deliveries for %s/%s' % key)
        logs[key] = row
    for (shard, offset), row in logs.items():
        txn = table.get(row['transaction'])
        if txn is None or not any(p['shard'] == shard and p['first'] <= offset <= p['last'] for p in txn['parts']):
            raise ValueError('delivery %s/%s does not match the manifest' % (shard, offset))
    return logs
