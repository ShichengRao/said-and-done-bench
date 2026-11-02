from collections import defaultdict

def transform(bundle):
    cfg=bundle['request'];tenants=set(cfg['tenants']);as_of=cfg['as_of'];latest={};seen={}
    for row in bundle['tickets']:
        if row['tenant'] not in tenants or row['recorded']>as_of:continue
        key=(row['tenant'],row['id'],row['revision'])
        if key in seen and seen[key]!=row:raise ValueError('conflicting ticket revision')
        seen[key]=row;entity=key[:2]
        if entity not in latest or row['revision']>latest[entity]['revision']:latest[entity]=row
    def resolve(tenant,external,at):
        reachable={('support',external)}
        while True:
            expanded=reachable|{tuple(row['target']) for row in bundle['bridge'] if row['tenant']==tenant and row['purpose']==cfg['purpose'] and row['from']<=at and (row['until'] is None or at<row['until']) and tuple(row['source']) in reachable}
            if expanded==reachable:break
            reachable=expanded
        ids={value for kind,value in reachable if kind=='crm'}
        if len(ids)!=1:raise ValueError('unresolved identity bridge')
        return next(iter(ids))
    def revision(rows,tenant,customer,at,kind):
        filtered={}
        for row in rows:
            if row['tenant']!=tenant or row['customer']!=customer or row['at']>at:continue
            if kind=='consent' and row['purpose']!=cfg['purpose']:continue
            if row['seq'] in filtered and filtered[row['seq']]!=row:raise ValueError('conflicting '+kind+' revision')
            filtered[row['seq']]=row
        return filtered[max(filtered)] if filtered else None
    groups={};excluded={'deleted':0,'status':0,'consent_at_event':0,'consent_now':0}
    for (tenant,_),ticket in sorted(latest.items()):
        if ticket['deleted']:excluded['deleted']+=1;continue
        if ticket['status'] not in cfg['statuses']:excluded['status']+=1;continue
        customer=resolve(tenant,ticket['external'],ticket['at'])
        event_consent=revision(bundle['consent'],tenant,customer,ticket['at'],'consent')
        if event_consent is None or not event_consent['allow']:excluded['consent_at_event']+=1;continue
        now_consent=revision(bundle['consent'],tenant,customer,as_of,'consent')
        if now_consent is None or not now_consent['allow']:excluded['consent_now']+=1;continue
        crm=revision(bundle['crm'],tenant,customer,ticket['at'],'crm')
        if crm is None:raise ValueError('missing CRM revision')
        key=(tenant,crm['region'],crm['segment'])
        if key not in groups:groups[key]={'members':set(),'tickets':0}
        groups[key]['members'].add(customer);groups[key]['tickets']+=1
    reasons={key:'small_group' for key,value in groups.items() if len(value['members'])<cfg['k']}
    partitions=defaultdict(list)
    for key in groups:partitions[key[:2]].append(key)
    regions=[]
    for partition,keys in sorted(partitions.items()):
        suppressed=[key for key in keys if key in reasons];visible=[key for key in keys if key not in reasons]
        if False:
            chosen=min(visible,key=lambda key:(len(groups[key]['members']),key[2]));reasons[chosen]='complementary'
        members=set().union(*(groups[key]['members'] for key in keys));tickets=sum(groups[key]['tickets'] for key in keys)
        hidden=len(members)<cfg['k'] or (len(keys)==1 and keys[0] in reasons)
        regions.append({'tenant':partition[0],'region':partition[1],'members':None if hidden else len(members),'tickets':None if hidden else tickets})
    cohorts=[{'tenant':key[0],'region':key[1],'segment':key[2],'members':None if key in reasons else len(value['members']),'tickets':None if key in reasons else value['tickets'],'suppression':reasons.get(key)} for key,value in sorted(groups.items())]
    return {'cohorts':cohorts,'regions':regions,'excluded':excluded,'blocker_codes':[]}

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
