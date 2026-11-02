"""Load and validate a delivery batch directory."""
import json
from pathlib import Path

KINDS = {'owner_change', 'revoke', 'grant', 'copy', 'receipt'}


def load_batch(root):
    root = Path(root)

    def read(name):
        return json.loads((root / name).read_text())

    meta = read('batch.json')
    batch = {
        'batch': meta['batch'],
        'customer': meta['customer'],
        'records': read('records.json'),
        'credentials': read('credentials.json'),
        'exports': [read('exports/%s.json' % name) for name in meta['exports']],
        'ordering': read('ordering.json')['attestations'],
    }
    validate(batch)
    return batch


def events(batch):
    return [event for export in batch['exports'] for event in export['events']]


def validate(batch):
    """Reject duplicate or unknown references; shapes are otherwise trusted."""
    flat = events(batch)
    issued = batch['credentials']['issued']
    names = [e['id'] for e in flat] + [c['id'] for c in issued]
    if len(names) != len(set(names)):
        raise ValueError('duplicate event or credential ID')
    by_id = {e['id']: e for e in flat}
    slots = batch['credentials']['slots']
    credentials = {c['id'] for c in issued} | {e['id'] for e in flat if e['kind'] == 'grant'}
    copies = {e['id'] for e in flat if e['kind'] == 'copy'}
    for credential in issued:
        if credential['slot'] not in slots or (credential['parent'] is not None and credential['parent'] not in credentials):
            raise ValueError('unknown credential reference in %s' % credential['id'])
    for name, slot in slots.items():
        if slot['current'] is not None and slot['current'] not in {c['id'] for c in issued if c['slot'] == name}:
            raise ValueError('unknown current credential for slot %s' % name)
    for event in flat:
        kind = event['kind']
        if kind not in KINDS:
            raise ValueError('unknown event kind %s' % kind)
        if kind == 'owner_change' and event['record'] not in batch['records']:
            raise ValueError('unknown record in %s' % event['id'])
        if kind in ('grant', 'revoke') and event['slot'] not in slots:
            raise ValueError('unknown slot in %s' % event['id'])
        if kind == 'grant' and event['parent'] is not None and event['parent'] not in credentials:
            raise ValueError('unknown parent in %s' % event['id'])
        if kind == 'copy':
            source = event['source']
            if source['kind'] == 'record':
                if source['id'] not in batch['records'] or event.get('slot') not in slots:
                    raise ValueError('unknown copy source in %s' % event['id'])
            elif source['id'] not in copies:
                raise ValueError('unknown source copy in %s' % event['id'])
        if kind == 'receipt' and event['copy'] not in copies:
            raise ValueError('unknown delivered copy in %s' % event['id'])
    for attestation in batch['ordering']:
        if attestation['earlier'] not in by_id or attestation['later'] not in by_id:
            raise ValueError('ordering attestation names an unknown event')
