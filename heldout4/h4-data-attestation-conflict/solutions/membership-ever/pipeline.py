import hashlib
import json

def transform(data):
    previous = '0' * 64
    for event in data['audit_chain']:
        if event['previous'] != previous: raise ValueError('broken audit link')
        body = {k:v for k,v in event.items() if k != 'hash'}
        digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if digest != event['hash']: raise ValueError('audit hash mismatch')
        previous=event['hash']
    resources={(r['tenant'],r['id']):r for r in data['resources']}
    exposures=[]; delivered=0
    for event in data['audit_chain']:
        if event['status'] != 200 or event['bytes'] <= 0: continue
        delivered += 1
        resource=resources[(event['resource_tenant'],event['resource'])]
        reasons=[]
        if event['principal_tenant'] != event['resource_tenant']:
            reasons.append('cross-tenant')
        latest={}
        for grant in data['membership_events']:
            if not grant['member'] or grant['tenant']!=event['principal_tenant'] or grant['user']!=event['user'] or grant['at']>event['at']: continue
            order=(grant['at'],grant['sequence'])
            if grant['group'] not in latest or order>latest[grant['group']][0]:
                latest[grant['group']]=(order,grant['member'])
        groups={group for group,(_,member) in latest.items() if member}
        if not groups.intersection(resource['allowed_groups']): reasons.append('missing-membership')
        if reasons: exposures.append({'audit_id':event['id'],'resource':event['resource'],'reasons':reasons})
    return {'chain_head':previous,'delivered_responses':delivered,'exposures':exposures,
            'attestation_supported':not exposures,
            'blocker_codes':['ATTESTATION_CONTRADICTED'] if exposures else []}

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
