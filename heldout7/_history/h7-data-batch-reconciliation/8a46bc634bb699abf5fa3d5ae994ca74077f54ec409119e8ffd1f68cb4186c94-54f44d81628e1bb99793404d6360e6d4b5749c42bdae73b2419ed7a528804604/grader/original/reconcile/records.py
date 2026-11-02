"""Loading and reference checks for the batch and reservation ledger."""
import json
from pathlib import Path


def load(root):
    root = Path(root)
    batch = json.loads((root / 'batch.json').read_text())
    ledger = json.loads((root / 'ledger.json').read_text())
    return batch, ledger


def collapse(rows, kind):
    """Identical replays collapse; a changed payload under one ID is an error."""
    result = {}
    for row in rows:
        if row['id'] in result and result[row['id']] != row:
            raise ValueError('conflicting %s replay %s' % (kind, row['id']))
        result[row['id']] = row
    return result


def credentials(batch):
    table = {c['id']: c for c in batch['credentials']}
    if len(table) != len(batch['credentials']):
        raise ValueError('duplicate credential ID')
    if len({r['id'] for r in batch['routes']}) != len(batch['routes']):
        raise ValueError('duplicate route ID')
    for c in table.values():
        if c['pool'] not in batch['budgets']:
            raise ValueError('credential %s uses unknown pool' % c['id'])
        if c['parent'] is not None and c['parent'] not in table:
            raise ValueError('credential %s has unknown parent' % c['id'])
    for route in batch['routes']:
        if any(name not in table for name in route['credentials']):
            raise ValueError('route %s names unknown credential' % route['id'])
    return table
