"""Resolve the current signed settlement instructions (docs/settlement_instructions.md)."""
import copy

META = ('revision', 'known', 'signed', 'void')
DEPENDENCIES = ('receipt_after', 'activate_after', 'release_after')


def resolve(batch):
    result = {}
    for stream in ('owners', 'payouts', 'bridges'):
        seen = {}; selected = {}
        for row in batch[stream]:
            key = (row['id'], row['revision'])
            if key in seen and seen[key] != row:
                raise ValueError('conflicting %s instruction %s revision %s' % (stream, *key))
            seen[key] = row
            if row['signed'] and (row['id'] not in selected or row['revision'] > selected[row['id']]['revision']):
                selected[row['id']] = row
        rows = [{k: copy.deepcopy(v) for k, v in r.items() if k not in META} for r in selected.values() if not r['void']]
        rows.sort(key=lambda r: r['id'])
        for r in rows:
            for k in DEPENDENCIES:
                if k in r:
                    r[k] = sorted(r[k])
        result[stream] = {r['id']: r['wallet'] for r in rows} if stream == 'owners' else rows
    return result
