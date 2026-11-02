from itertools import combinations

def transform(bundle):
    catalog=bundle['catalog'];topology=bundle['topology'];reservations=bundle['reservations']
    at=catalog['at']; nodes={r['id']:r for r in topology}; datasets={r['id']:r for r in catalog['datasets']}
    if len(nodes)!=len(topology) or len(datasets)!=len(catalog['datasets']):raise ValueError('duplicate identity')
    sizes={};options={};candidates={}
    for key,d in sorted(datasets.items()):
        chunks={};seen={}
        for row in d['chunks']:
            if row['seq']>d['barrier']:continue
            revision=(row['id'],row['seq'])
            if revision in seen and seen[revision]!=row:raise ValueError('conflicting chunk revision')
            seen[revision]=row
            old=chunks.get(row['id'])
            if old and old['seq']==row['seq'] and old!=row:raise ValueError('conflicting chunk revision')
            if old is None or old['seq']<row['seq']:chunks[row['id']]=row
        sizes[key]=sum(r['bytes'] for r in chunks.values() if r['op']=='put')
        eligible=sorted(n for n,r in nodes.items() if r['region'] in d['regions'] and d['key'] in r['keys'] and r['cdc'])
        candidates[key]=eligible
        options[key]=[tuple(c) for c in combinations(eligible,d['replicas']) if len({nodes[n]['domain'] for n in c})==d['replicas']]
    reservations_by_id={}
    for row in reservations:
        old=reservations_by_id.get(row['id'])
        if old is not None and old!=row:raise ValueError('conflicting reservation')
        if row['node'] not in nodes:raise ValueError('unknown reservation node')
        reservations_by_id[row['id']]=row
    capacity={n:r['capacity'] for n,r in nodes.items()}
    for row in reservations_by_id.values():
        if row['from']<=at and (row['until'] is None or at<row['until']):capacity[row['node']]-=row['bytes']
    if any(v<0 for v in capacity.values()):raise ValueError('overreserved node')
    def search(keys,augment=False):
        best=None;used={n:0 for n in nodes}
        def visit(i,selected):
            nonlocal best
            cost=sum(max(0,used[n]-capacity[n]) for n in nodes)
            if not augment and cost:return
            if best is not None and cost>best[0]:return
            if i==len(keys):
                signature=tuple((key,tuple(selected[key])) for key in keys)
                value=(cost,signature,dict(used))
                if best is None or value[:2]<best[:2]:best=value
                return
            key=keys[i]
            for combo in options[key]:
                for n in combo:used[n]+=sizes[key]
                selected[key]=combo;visit(i+1,selected)
                for n in combo:used[n]-=sizes[key]
            selected.pop(key,None)
        visit(0,{})
        return best
    keys=sorted(datasets);solution=search(keys)
    def placement(result):return [{'dataset':key,'nodes':list(combo)} for key,combo in result[1]]
    core=[];repair=None
    if solution is None:
        for count in range(1,len(keys)+1):
            found=False
            for subset in combinations(keys,count):
                if search(list(subset)) is None:core=list(subset);found=True;break
            if found:break
        augmented=search(keys,True)
        if augmented is not None:
            repair={'total_bytes':augmented[0],'extra_bytes':{n:max(0,augmented[2][n]-capacity[n]) for n in sorted(nodes) if augmented[2][n]>capacity[n]},'placement':placement(augmented)}
    return {'ready':solution is not None,'dataset_bytes':sizes,'available_bytes':dict(sorted(capacity.items())),'candidates':candidates,'placement':placement(solution) if solution else [],'infeasible_core':core,'capacity_remedy':repair,'blocker_codes':[] if solution else ['allocation_infeasible']}

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
