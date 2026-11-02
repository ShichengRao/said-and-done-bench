from itertools import combinations

def transform(bundle):
    request=bundle['request'];at=request['at'];owners={r['id']:r for r in bundle['owners']};groups={r['id']:r for r in request['groups']}
    events={}
    for row in bundle['authority']:
        if row['at']>at:continue
        key=row['seq']
        if key in events and events[key]!=row:raise ValueError('conflicting authority event')
        events[key]=row
    active={}
    for seq,row in sorted(events.items()):
        key=(row['owner'],row['scope'])
        if row['op']=='grant':active[key]=row['until']
        else:active.pop(key,None)
    candidates={key:sorted(owner for owner in owners if owners[owner]['from']<=at and (owners[owner]['until'] is None or at<owners[owner]['until']) and all((owner,scope) in active and (active[(owner,scope)] is None or at<active[(owner,scope)]) for scope in group['scopes'])) for key,group in sorted(groups.items())}
    capacity={key:row['capacity'] for key,row in owners.items()}
    for row in bundle['reservations']:
        if row['from']<=at and (row['until'] is None or at<row['until']):capacity[row['owner']]-=row['units']
    if any(v<0 for v in capacity.values()):raise ValueError('overreserved owner')
    separation={frozenset(pair) for pair in request['separate']}
    def solve(keys,options):
        used={o:0 for o in owners};chosen={}
        def visit(i):
            if i==len(keys):return dict(chosen)
            key=keys[i]
            for owner in options[key]:
                if used[owner]+groups[key]['units']>capacity[owner]:continue
                if False:continue
                chosen[key]=owner;used[owner]+=groups[key]['units']
                result=visit(i+1)
                if result is not None:return result
                used[owner]-=groups[key]['units'];chosen.pop(key)
            return None
        return visit(0)
    keys=sorted(groups);assignment=solve(keys,candidates);core=[];remedy=None
    if assignment is None:
        for count in range(1,len(keys)+1):
            for subset in combinations(keys,count):
                if solve(list(subset),candidates) is None:core=list(subset);break
            if core:break
        proposals=sorted(bundle['proposals'],key=lambda p:p['id']);best=None
        for count in range(1,len(proposals)+1):
            for selected in combinations(proposals,count):
                options={k:list(v) for k,v in candidates.items()}
                for p in selected:
                    owner=p['owner']
                    if owners[owner]['from']<=at and (owners[owner]['until'] is None or at<owners[owner]['until']):options[p['group']]=sorted(set(options[p['group']]+[owner]))
                found=solve(keys,options)
                if found is None:continue
                score=(sum(p['cost'] for p in selected),tuple(p['id'] for p in selected))
                if best is None or score<best[0]:best=(score,found)
        if best:remedy={'proposals':list(best[0][1]),'cost':best[0][0],'assignment':best[1]}
    return {'ready':assignment is not None,'candidates':candidates,'available_units':dict(sorted(capacity.items())),'assignment':assignment or {},'infeasible_core':core,'owner_remedy':remedy,'blocker_codes':[] if assignment is not None else ['owner_assignment_infeasible']}

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
