from copy import deepcopy

def transform(bundle):
    catalog=bundle['catalog'];cut=catalog['cutover'];versions={};heads={}
    for row in catalog['versions']:
        if row['version'] in versions and versions[row['version']]!=row:raise ValueError('conflicting version')
        versions[row['version']]=deepcopy(row)
    events={}
    for row in bundle['changes']:
        if row['seq']>cut:continue
        if row['seq'] in events and events[row['seq']]!=row:raise ValueError('conflicting sequence')
        events[row['seq']]=row
    for obj,ver in catalog['heads'].items():
        if ver not in versions or versions[ver]['object']!=obj:raise ValueError('invalid snapshot head')
        heads[obj]=ver
    for seq,row in sorted(events.items()):
        if seq<=catalog['watermark']:continue
        obj=row['object']
        if row['op']=='delete':heads.pop(obj,None)
        else:
            value=row['value'];ver=value['version']
            if value['object']!=obj:raise ValueError('object mismatch')
            if ver in versions and versions[ver]!=value:raise ValueError('conflicting version')
            versions[ver]=deepcopy(value);heads[obj]=ver
    memo={};visiting=set()
    def ancestors(ver):
        if ver not in versions:raise ValueError('missing lineage version')
        if ver in visiting:raise ValueError('lineage cycle')
        if ver in memo:return memo[ver]
        visiting.add(ver);closure={ver}
        for parent in versions[ver]['parents']:closure|=ancestors(parent)
        visiting.remove(ver);memo[ver]=closure;return closure
    for ver in versions:ancestors(ver)
    direct={ver:set() for ver in versions}
    for ver,row in versions.items():
        for identity in row['identities']:
            matches={b['subject'] for b in bundle['identity'] if b['tenant']==identity['tenant'] and b['alias']==identity['alias'] and b['from']<=identity['at'] and (b['until'] is None or identity['at']<b['until'])}
            if len(matches)!=1:raise ValueError('ambiguous or missing identity')
            subject=next(iter(matches))
            for request in bundle['requests']:
                if request['tenant']==identity['tenant'] and request['subject']==subject and identity['at']<=request['through']:
                    direct[ver].add(request['id'])
    tainted={ver:sorted(set().union(*(direct[parent] for parent in ancestors(ver)))) for ver in versions}
    tainted={ver:requests for ver,requests in tainted.items() if requests}
    held={}
    for hold in bundle['holds']:
        if hold['from']<=catalog['at'] and (hold['until'] is None or catalog['at']<hold['until']):
            for ver in ancestors(hold['version']):held.setdefault(ver,set()).add(hold['id'])
    suppressed=[{'object':obj,'version':ver,'requests':tainted[ver]} for obj,ver in sorted(heads.items()) if ver in tainted and ver not in held]
    survivors=[deepcopy(versions[ver]) for obj,ver in sorted(heads.items()) if ver not in tainted or ver in held]
    retained=[{'version':ver,'holds':sorted(held[ver]),'requests':tainted[ver]} for ver in sorted(tainted) if ver in held]
    return {'survivors':survivors,'suppressed':suppressed,'purge_versions':sorted(set(tainted)-set(held)),'retained_for_hold':retained,'tainted_versions':[{'version':ver,'requests':tainted[ver]} for ver in sorted(tainted)],'blocker_codes':[]}

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
