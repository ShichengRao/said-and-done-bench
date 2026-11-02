import copy

def transform(data):
    now = data['as_of']
    requests = {}
    for request in data['requests']:
        if request['effective'] <= now:
            key = (request['tenant'], request['subject'])
            requests[key] = max(requests.get(key, -1), request['effective'])
    kept, receipts = [], []
    for original in sorted(data['records'], key=lambda r:(r['tenant'],r['id'])):
        row = copy.deepcopy(original)
        key = (row['tenant'], row['subject'])
        cutoff = requests.get(key)
        erased, retained = [], []
        for field in sorted(row['fields']):
            item = row['fields'][field]
            if cutoff is None:
                continue
            holds = sorted(h['id'] for h in data['holds']
                if h['tenant'] == row['tenant'] and h['subject'] == row['subject']
                and item['class'] in h['classes'] and h['starts'] <= now
                and (h['ends'] is None or now < h['ends']))
            if holds:
                retained.append({'field':field,'hold_ids':holds})
            else:
                erased.append(field)
                del row['fields'][field]
        if row['fields']:
            kept.append(row)
        if cutoff is not None:
            receipts.append({'tenant':row['tenant'],'record_id':row['id'],
                             'erased_fields':erased,'retained_fields':retained,
                             'removed_record':not bool(row['fields'])})
    return {'records':kept,'receipts':receipts}

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
