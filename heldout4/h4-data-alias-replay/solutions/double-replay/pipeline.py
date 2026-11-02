import copy

def transform(data):
    customers = {(c['tenant'], c['id']): copy.deepcopy(c) for c in data['customers']}
    if len(customers) != len(data['customers']):
        raise ValueError('duplicate customer key')
    events = {}
    duplicates = 0
    for event in data['events']:
        key = (event['tenant'], event['event_id'])
        if key in events:
            if events[key] != event:
                raise ValueError('conflicting event id')
            duplicates += 1
            events[(event['tenant'], event['event_id'] + '-duplicate')] = event
        else:
            events[key] = event
    applied = []
    for event in sorted(events.values(), key=lambda e: (e['sequence'], e['tenant'], e['event_id'])):
        matches = {b['customer_id'] for b in data['bindings']
                   if b['tenant'] == event['tenant'] and b['alias'] == event['alias']
                   and b['from'] <= event['at'] and (b['until'] is None or event['at'] < b['until'])}
        if len(matches) != 1:
            raise ValueError('unresolved or ambiguous alias')
        key = (event['tenant'], matches.pop())
        if key not in customers:
            raise ValueError('unknown customer')
        customer = customers[key]
        if event['kind'] == 'seats_delta':
            customer['seats'] += event['value']
            if customer['seats'] < 0:
                raise ValueError('negative seats')
        elif event['kind'] == 'tier':
            customer['tier'] = event['value']
        elif event['kind'] == 'close':
            customer['active'] = False
        else:
            raise ValueError('unknown event kind')
        applied.append({'tenant': event['tenant'], 'event_id': event['event_id'], 'customer_id': key[1]})
    return {'customers': [customers[key] for key in sorted(customers)],
            'applied': applied, 'duplicate_deliveries': duplicates}

import argparse
import json
import os
import tempfile
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='data/input.json')
    parser.add_argument('--output', default='output/report.json')
    args = parser.parse_args()
    result = transform(json.loads(Path(args.input).read_text()))
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=destination.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write('\n')
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

if __name__ == '__main__':
    main()
