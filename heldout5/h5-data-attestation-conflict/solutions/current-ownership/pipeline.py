import hashlib,json

def transform(bundle):
    manifest=bundle['manifest'];receipts={}
    for row in bundle['receipts']:
        if row['seq'] in receipts and receipts[row['seq']]!=row:raise ValueError('conflicting receipt')
        receipts[row['seq']]=row
    if sorted(receipts)!=list(range(1,manifest['count']+1)):raise ValueError('incomplete receipt stream')
    previous='0'*64
    for seq,row in sorted(receipts.items()):
        if row['previous']!=previous:raise ValueError('broken receipt chain')
        payload={k:v for k,v in row.items() if k!='digest'}
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if row['digest']!=digest:raise ValueError('receipt digest mismatch')
        previous=digest
    if previous!=manifest['root']:raise ValueError('manifest root mismatch')
    artifacts={row['id']:row for row in bundle['artifacts']};attempts={row['id']:row for row in bundle['attempts']};requests={row['id']:row for row in bundle['requests']}
    memo={};visiting=set()
    def sources(key):
        if key not in artifacts or key in visiting:raise ValueError('invalid artifact lineage')
        if key in memo:return memo[key]
        visiting.add(key);row=artifacts[key];result=set()
        for logical in row['logical']:
            tenants={r['tenant'] for r in bundle['ownership'] if r['logical']==logical and r['until'] is None}
            if len(tenants)!=1:raise ValueError('unresolved source ownership')
            result.add((key,logical,next(iter(tenants))))
        for parent in row['parents']:
            if parent not in artifacts or artifacts[parent]['created']>row['created']:raise ValueError('noncausal lineage')
            result|=sources(parent)
        visiting.remove(key);memo[key]=result;return result
    for key in artifacts:sources(key)
    def allowed(principal,at):
        events={}
        for row in bundle['memberships']:
            if row['principal']!=principal or row['at']>at:continue
            if row['seq'] in events and events[row['seq']]!=row:raise ValueError('conflicting membership')
            events[row['seq']]=row
        groups={}
        for _,row in sorted(events.items()):
            if row['op']=='grant':groups[row['group']]=row['until']
            else:groups.pop(row['group'],None)
        return {p['tenant'] for p in bundle['policy'] if p['group'] in groups and (groups[p['group']] is None or at<groups[p['group']])}
    checks=[];violations=[];replays=[]
    for seq,receipt in sorted(receipts.items()):
        if not receipt['ack']:continue
        if receipt['attempt'] not in attempts:raise ValueError('missing accepted attempt')
        attempt=attempts[receipt['attempt']]
        if attempt['request'] not in requests:raise ValueError('missing request')
        request=requests[attempt['request']];artifact=attempt['artifact']
        if artifact not in artifacts or artifacts[artifact]['created']>receipt['at']:raise ValueError('noncausal delivery')
        rights=allowed(request['principal'],receipt['at']);origin=sorted(sources(artifact))
        denied=[list(item) for item in origin if item[2] not in rights]
        checks.append({'receipt':seq,'request':request['id'],'attempt':attempt['id'],'sources':[list(item) for item in origin],'unauthorized':denied})
        if denied:
            violations.append(seq);possible=[];at=request['replay_at'];rights=allowed(request['principal'],at)
            for replacement in bundle['replacements']:
                if replacement['request']==request['id'] and replacement['artifact'] in artifacts and artifacts[replacement['artifact']]['created']<=at and all(item[2] in rights for item in sources(replacement['artifact'])):possible.append(replacement['artifact'])
            replays.append({'receipt':seq,'at':at,'artifact':min(possible) if possible else None})
    return {'certifiable':not violations,'receipt_checks':checks,'violations':violations,'safe_replays':replays,'blocker_codes':[] if not violations else ['historical_delivery_unauthorized']}

import argparse
import json
import os
import tempfile
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input', default='data')
    parser.add_argument('--output', default='output/report.json')
    args=parser.parse_args()
    bundle={p.stem:json.loads(p.read_text()) for p in sorted(Path(args.input).glob('*.json'))}
    result=transform(bundle)
    destination=Path(args.output); destination.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=destination.parent)
    try:
        with os.fdopen(fd,'w') as stream: json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
        os.replace(name,destination)
    finally:
        if os.path.exists(name): os.unlink(name)
if __name__=='__main__': main()
