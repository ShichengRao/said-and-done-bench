from copy import deepcopy
from itertools import combinations


def transform(bundle):
    s=bundle['schedule'];ledger=bundle['ledger'];at=s['as_of'];times=sorted(s['slots'])
    credentials={x['id']:x for x in s['credentials']}
    if len(credentials)!=len(s['credentials']) or len({x['id'] for x in s['routes']})!=len(s['routes']):raise ValueError('duplicate credential or route')
    def unique(rows):
        out={}
        for row in rows:
            if row['id'] in out and out[row['id']]!=row:raise ValueError('conflicting replay')
            out[row['id']]=row
        return out
    attempts=unique(ledger['attempts']);receipts=unique(ledger['receipts'])
    for c in credentials.values():
        if c['pool'] not in s['budgets'] or c['parent'] is not None and c['parent'] not in credentials:raise ValueError('unknown credential parent or pool')
    for r in s['routes']:
        if any(c not in credentials for c in r['credentials']):raise ValueError('unknown route credential')
    for a in attempts.values():
        if any(c not in credentials for c in a['credentials']):raise ValueError('unknown attempted credential')
    declared={r['reservation'] for r in receipts.values() if r['kind']=='reserve'}
    for r in receipts.values():
        if r['kind'] in ('reserve','reject') and r['attempt'] not in attempts:raise ValueError('unknown attempt')
        if r['kind'] in ('commit','release') and r['reservation'] not in declared:raise ValueError('unknown reservation')
    reservations={};keys={}
    for r in sorted(receipts.values(),key=lambda x:(x['at'],x['id'])):
        if r['at']>at:continue
        kind=r['kind']
        if kind in ('reserve','reject'):
            a=attempts[r['attempt']]
            if a['at']>r['at']:raise ValueError('receipt before attempt')
        if kind=='reject':continue
        name=r['reservation']
        if kind=='reserve':
            value={'key':a['key'],'attempt':a['id'],'units':a['units'],'pools':sorted({credentials[c]['pool'] for c in a['credentials']}),'expires':r['expires']}
            if name in reservations:
                if reservations[name]['binding']!=value:raise ValueError('conflicting reservation binding')
            else:
                if a['key'] in keys or r['expires']<=r['at']:raise ValueError('conflicting key or expired new reservation')
                keys[a['key']]=name;reservations[name]={'binding':value,'state':'held'}
        else:
            if name not in reservations:raise ValueError('terminal before reservation')
            state=reservations[name]
            target='committed' if kind=='commit' else 'released'
            if state['state'] not in ('held',target):raise ValueError('conflicting terminal receipts')
            if kind=='commit' and state['state']=='held' and r['at']>=state['binding']['expires']:raise ValueError('commit after expiry')
            state['state']=target
    resolved={}
    for name,value in sorted(reservations.items()):
        state=value['state'];binding=value['binding']
        if state=='held' and binding['expires']<=at:state='expired'
        resolved[name]={**binding,'state':state}
    rejected={attempts[r['attempt']]['key'] for r in receipts.values() if r['kind']=='reject' and r['at']<=at}
    for row in resolved.values():
        if row['key'] in rejected:row['state']='released'
    availability={p:{str(t):s['budgets'][p]-sum(r['units'] for r in resolved.values() if p in r['pools'] and (r['state']=='committed' or r['state']=='held' and t<r['expires'])) for t in times} for p in sorted(s['budgets'])}
    requests=sorted(s['requests'],key=lambda q:q['id']);options={q['id']:[] for q in requests}
    for q in requests:
        for route in sorted(s['routes'],key=lambda r:r['id']):
            if route['request']!=q['id']:continue
            chain=[credentials[c] for c in route['credentials']]
            if not chain or chain[0]['parent'] is not None or chain[-1]['id'] not in q['leaves']:continue
            if any(b['parent']!=a['id'] for a,b in zip(chain,chain[1:])):continue
            if any(not set(q['scopes'])<=set(c['scopes']) for c in chain):continue
            for t in times:
                if t<q['earliest'] or t+q['duration']>q['latest']:continue
                if any(t<c['start'] or t+q['duration']>c['end'] for c in chain):continue
                options[q['id']].append({'route':route['id'],'slot':t,'pools':sorted({c['pool'] for c in chain})})
    def solve(qs,props=()):
        remaining=deepcopy(availability);workers=dict(s['workers']);answer={}
        for p in props:
            if p['kind']=='budget':
                for t in times:remaining[p['pool']][str(t)]+=p['units']
            else:workers[str(p['slot'])]+=p['units']
        def visit(i):
            if i==len(qs):return deepcopy(answer)
            q=qs[i];units=q['units']
            for option in options[q['id']]:
                slot=option['slot'];later=[str(t) for t in times if t>=slot]
                if workers[str(slot)]<units or any(remaining[p][t]<units for p in option['pools'] for t in later):continue
                workers[str(slot)]-=units
                for p in option['pools']:
                    for t in later:remaining[p][t]-=units
                answer[q['id']]={'route':option['route'],'slot':slot}
                result=visit(i+1)
                if result is not None:return result
                workers[str(slot)]+=units
                for p in option['pools']:
                    for t in later:remaining[p][t]+=units
                answer.pop(q['id'])
            return None
        return visit(0)
    assignment=solve(requests);obstruction=[]
    if assignment is None:
        for n in range(1,len(requests)+1):
            bad=next(([q['id'] for q in qs] for qs in combinations(requests,n) if solve(qs) is None),None)
            if bad is not None:obstruction=bad;break
    proposals=sorted(bundle['proposals'],key=lambda p:p['id']);repairs=[]
    for n in range(len(proposals)+1):
        for chosen in combinations(proposals,n):
            witness=solve(requests,chosen)
            if witness is not None:
                ids=[p['id'] for p in chosen];cost=sum(p['cost'] for p in chosen)
                repairs.append(((cost,n,ids),{'proposal_ids':ids,'cost':cost,'assignment':witness}))
    return {'ready':assignment is not None,'reservation_state':resolved,'availability':availability,'route_options':options,'assignment':assignment,'obstruction':obstruction,'owner_request':min(repairs,key=lambda x:x[0])[1] if repairs else None,'blocker_codes':[] if assignment is not None else ['batch_delegation_budget_required']}

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
