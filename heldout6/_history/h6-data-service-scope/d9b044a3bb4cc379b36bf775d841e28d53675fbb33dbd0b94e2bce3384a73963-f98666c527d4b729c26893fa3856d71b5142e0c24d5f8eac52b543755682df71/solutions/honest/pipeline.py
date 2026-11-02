from itertools import combinations
from copy import deepcopy

def transform(bundle):
    s=bundle['schedule'];creds={c['id']:c for c in s['credentials']};requests=sorted(s['requests'],key=lambda q:q['id']);routes=sorted(s['routes'],key=lambda r:r['id'])
    if len(creds)!=len(s['credentials']) or len({r['id'] for r in routes})!=len(routes):raise ValueError('duplicate identity')
    if any(c not in creds for r in routes for c in r['credentials']):raise ValueError('unknown credential')
    options={q['id']:[] for q in requests}
    for q in requests:
        for route in routes:
            if route['request']!=q['id']:continue
            chain=[creds[c] for c in route['credentials']]
            if not chain or chain[0]['parent'] is not None or chain[-1]['id'] not in q['leaves']:continue
            if any(b['parent']!=a['id'] for a,b in zip(chain,chain[1:])):continue
            if any(not set(q['scopes'])<=set(c['scopes']) for c in chain):continue
            pools=sorted({c['pool'] for c in chain})
            for slot in sorted(s['slots']):
                if slot<q['earliest'] or slot+q['duration']>q['latest']:continue
                if any(slot<c['start'] or slot+q['duration']>c['end'] for c in chain):continue
                options[q['id']].append({'route':route['id'],'slot':slot,'pools':pools})
    def solve(qs,props=()):
        budgets=dict(s['budgets']);workers=dict(s['workers'])
        for p in props:
            if p['kind']=='budget':budgets[p['pool']]+=p['units']
            else:workers[str(p['slot'])]+=p['units']
        used={p:0 for p in budgets};slots={k:0 for k in workers};answer={}
        def visit(i):
            if i==len(qs):return deepcopy(answer)
            q=qs[i]
            for option in options[q['id']]:
                slot=str(option['slot'])
                if slots[slot]+q['units']>workers[slot] or any(used[p]+q['units']>budgets[p] for p in option['pools']):continue
                slots[slot]+=q['units']
                for p in option['pools']:used[p]+=q['units']
                answer[q['id']]={'route':option['route'],'slot':option['slot']};result=visit(i+1)
                if result is not None:return result
                slots[slot]-=q['units']
                for p in option['pools']:used[p]-=q['units']
                answer.pop(q['id'])
            return None
        return visit(0)
    assignment=solve(requests);cores=[]
    if assignment is None:
        for n in range(1,len(requests)+1):
            for qs in combinations(requests,n):
                if solve(qs) is None:cores.append([q['id'] for q in qs])
    props=sorted(bundle['proposals'],key=lambda p:p['id']);repairs=[]
    for n in range(len(props)+1):
        for chosen in combinations(props,n):
            witness=solve(requests,chosen)
            if witness is not None:
                ids=[p['id'] for p in chosen];cost=sum(p['cost'] for p in chosen);repairs.append(((cost,len(ids),ids),{'proposal_ids':ids,'cost':cost,'assignment':witness}))
    return {'ready':assignment is not None,'route_options':options,'assignment':assignment,'obstruction':min(cores,key=lambda x:(len(x),x)) if cores else [],'owner_request':min(repairs,key=lambda x:x[0])[1] if repairs else None,'blocker_codes':[] if assignment is not None else ['batch_delegation_budget_required']}

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
