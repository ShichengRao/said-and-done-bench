"""Revision ledger access."""
import json
from pathlib import Path


def load(data_dir):
    data_dir = Path(data_dir)
    cutover = json.loads((data_dir / 'cutover.json').read_text())
    entries = json.loads((data_dir / 'ledger.json').read_text())['entries']
    check_unique(entries)
    return cutover, entries


def check_unique(entries):
    seen = set()
    for row in entries:
        key = (row['kind'], row['entity'], row['revision'])
        if key in seen:
            raise ValueError('duplicate ledger revision %s/%s/%s' % key)
        seen.add(key)


def resolve(entries, kind, phase, cutoff):
    """Entity -> value of the highest approved revision recorded by `cutoff` and effective by `phase`."""
    chosen = {}
    for row in entries:
        if row['kind'] != kind or not row['approved'] or row['effective'] > phase:
            continue
        if row['entity'] not in chosen or row['revision'] > chosen[row['entity']]['revision']:
            chosen[row['entity']] = row
    return {entity: row['value'] for entity, row in chosen.items()}
