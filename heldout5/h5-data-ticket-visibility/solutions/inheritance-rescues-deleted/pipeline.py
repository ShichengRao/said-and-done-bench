import re
from copy import deepcopy

def transform(bundle):
    results=[]
    for query in sorted(bundle['queries'],key=lambda q:q['id']):
        tenant=query['tenant'];at=query['at'];revisions={};latest={}
        for row in bundle['documents']:
            if row['tenant']!=tenant or row['at']>at:continue
            key=(row['id'],row['seq'])
            if key in revisions and revisions[key]!=row:raise ValueError('conflicting document revision')
            revisions[key]=row
            if row['id'] not in latest or row['seq']>latest[row['id']]['seq']:latest[row['id']]=row
        ancestry={};visiting=set()
        def ancestors(key):
            if key not in latest or key in visiting:raise ValueError('broken document ancestry')
            if key in ancestry:return ancestry[key]
            visiting.add(key);row=latest[key]
            result=[key]+(ancestors(row['parent']) if row['parent'] is not None else [])
            visiting.remove(key);ancestry[key]=result;return result
        for key in latest:ancestors(key)
        events={}
        for row in bundle['membership']:
            if row['tenant']!=tenant or row['at']>at:continue
            if row['seq'] in events and events[row['seq']]!=row:raise ValueError('conflicting membership event')
            events[row['seq']]=row
        edges=set()
        for _,row in sorted(events.items()):
            edge=(row['member'],row['group'])
            if row['op']=='add':edges.add(edge)
            else:edges.discard(edge)
        principals={'u:'+query['user']}
        while True:
            expanded=principals|{group for member,group in edges if member in principals}
            if expanded==principals:break
            principals=expanded
        visible=[];hits=[]
        for key,row in sorted(latest.items()):
            if row['deleted']:continue
            allow=set();deny=set()
            for parent in ancestry[key]:
                acl=latest[parent];allow.update(acl['allow']);deny.update(acl['deny'])
                if not acl['inherit']:break
            if not (allow&principals) or deny&principals:continue
            visible.append(key)
            tokens=set(re.findall('[a-z0-9]+',row['content']['text'].lower()))
            if set(query['terms'])<=tokens:hits.append({'document':key,'revision':row['seq'],'content':deepcopy(row['content'])})
        results.append({'id':query['id'],'groups':sorted(p for p in principals if p.startswith('g:')),'visible':visible,'hits':hits})
    return {'queries':results,'blocker_codes':[]}

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
