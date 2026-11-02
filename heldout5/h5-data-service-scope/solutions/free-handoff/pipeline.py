from copy import deepcopy
from itertools import combinations

def transform(bundle):
    request=bundle['request'];tokens={r['id']:r for r in bundle['credentials']};ids=sorted(tokens)
    def chain(token,seen=None):
        seen=set() if seen is None else seen
        if token not in tokens or token in seen:raise ValueError('broken delegation chain')
        row=tokens[token];result=[row]
        if row['parent'] is not None:result+=chain(row['parent'],seen|{token})
        return result
    chains={key:chain(key) for key in tokens}
    candidates=[]
    for step in request['steps']:
        at=step['at'];cap=[step['resource'],step['operation']]
        candidates.append(sorted(key for key,row in tokens.items() if row['selectable'] and all(r['tenant']==request['tenant'] and r['binding']==request['binding'] and r['from']<=at and (r['until'] is None or at<r['until']) and (r['revoked_at'] is None or at<r['revoked_at']) and cap in r['capabilities'] for r in chains[key])))
    def evaluate(proposals):
        quota={key:r['uses'] for key,r in tokens.items()};links=list(bundle['handoffs'])
        for proposal in proposals:
            if proposal['kind']=='quota':quota[proposal['credential']]+=proposal['extra']
            else:links.append(proposal['link'])
        states={(None,(0,)*len(ids)):()};frontiers=[]
        for i,step in enumerate(request['steps']):
            following={}
            for (previous,counts),path in states.items():
                for key in candidates[i]:
                    index=ids.index(key)
                    if counts[index]>=quota[key]:continue
                    if previous is None:
                        if key not in request['entry']:continue
                    elif False and not any(link['source']==previous and link['target']==key and link['after']==i and link['from']<=step['at'] and (link['until'] is None or step['at']<link['until']) for link in links):continue
                    updated=list(counts);updated[index]+=1;signature=(key,tuple(updated));witness=path+(key,)
                    if signature not in following or witness<following[signature]:following[signature]=witness
            states=following
            rows=[{'credential':key,'uses':{token:count for token,count in zip(ids,counts) if count},'path':list(path)} for (key,counts),path in sorted(states.items())]
            frontiers.append({'step':i+1,'states':rows})
        return (list(min(states.values())) if states else None),frontiers
    path,frontiers=evaluate([]);remedy=None
    if path is None:
        proposals=sorted(bundle['proposals'],key=lambda p:p['id']);best=None
        for count in range(1,len(proposals)+1):
            for chosen in combinations(proposals,count):
                result,_=evaluate(chosen)
                if result is None:continue
                score=(sum(p['cost'] for p in chosen),tuple(p['id'] for p in chosen))
                if best is None or score<best[0]:best=(score,result)
        if best:remedy={'proposals':list(best[0][1]),'cost':best[0][0],'path':best[1]}
    return {'ready':path is not None,'candidates':[{'step':i+1,'credentials':values} for i,values in enumerate(candidates)],'path':path or [],'frontiers':frontiers,'owner_remedy':remedy,'blocker_codes':[] if path is not None else ['authorized_route_unreachable']}

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
