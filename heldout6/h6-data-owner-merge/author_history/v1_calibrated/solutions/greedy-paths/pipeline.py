from itertools import product,combinations
from copy import deepcopy

def transform(bundle):
    data=bundle['plan'];groups=sorted(data['groups'],key=lambda g:g['id']);phases=data['phases'];owners=sorted(data['capacity'])
    if len({g['id'] for g in groups})!=len(groups):raise ValueError('duplicate group')
    if any(o not in owners for g in groups for allowed in g['allowed'] for o in allowed):raise ValueError('unknown owner')
    def solve(chosen,proposals=()):
        capacity=deepcopy(data['capacity']);handoffs={g['id']:set(tuple(x) for x in g['handoffs']) for g in groups}
        for p in proposals:
            if p['kind']=='capacity':capacity[p['owner']][p['phase']]+=p['units']
            else:handoffs[p['group']].add((p['phase'],p['from'],p['to']))
        paths={g['id']:[list(path) for path in product(*[sorted(set(a)) for a in g['allowed']]) if all(a==b or (i,a,b) in handoffs[g['id']] for i,(a,b) in enumerate(zip(path,path[1:])))] for g in groups}
        usage={o:[0]*phases for o in owners};witness={}
        def visit(i):
            if i==len(chosen):return deepcopy(witness)
            g=chosen[i]
            for path in paths[g['id']][:1]:
                if any(usage[o][k]+g['load'][k]>capacity[o][k] for k,o in enumerate(path)):continue
                for k,o in enumerate(path):usage[o][k]+=g['load'][k]
                witness[g['id']]=path
                result=visit(i+1)
                if result is not None:return result
                for k,o in enumerate(path):usage[o][k]-=g['load'][k]
                witness.pop(g['id'])
            return None
        return visit(0),paths
    assignment,paths=solve(groups)
    per_phase=[]
    for k in range(phases):
        witness=None
        for vector in product(*[sorted(set(g['allowed'][k])) for g in groups]):
            if all(sum(g['load'][k] for g,o in zip(groups,vector) if o==owner)<=data['capacity'][owner][k] for owner in owners):
                witness=dict(zip([g['id'] for g in groups],vector));break
        per_phase.append(witness)
    core=[]
    if assignment is None:
        for n in range(1,len(groups)+1):
            found=False
            for chosen in combinations(groups,n):
                if solve(chosen)[0] is None:core=[g['id'] for g in chosen];found=True;break
            if found:break
    options=[];props=sorted(bundle['proposals'],key=lambda p:p['id'])
    for n in range(len(props)+1):
        for chosen in combinations(props,n):
            witness,_=solve(groups,chosen)
            if witness is not None:
                ids=[p['id'] for p in chosen];cost=sum(p['cost'] for p in chosen)
                options.append(((cost,len(ids),ids),{'proposal_ids':ids,'cost':cost,'assignment':witness}))
    request=min(options,key=lambda x:x[0])[1] if options else None
    return {'ready':assignment is not None,'local_paths':paths,'phase_witnesses':per_phase,'assignment':assignment,'obstruction':core,'owner_request':request,'blocker_codes':[] if assignment is not None else ['joint_stewardship_authority_required']}

import argparse,json,os,tempfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',default='data');p.add_argument('--output',default='output/report.json');a=p.parse_args()
    bundle={f.stem:json.loads(f.read_text()) for f in sorted(Path(a.input).glob('*.json'))}
    report=transform(bundle)
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=target.parent)
    try:
        with os.fdopen(fd,'w') as stream:json.dump(report,stream,sort_keys=True,indent=2);stream.write('\n')
        os.replace(name,target)
    finally:
        if os.path.exists(name):os.unlink(name)
if __name__=='__main__':main()
