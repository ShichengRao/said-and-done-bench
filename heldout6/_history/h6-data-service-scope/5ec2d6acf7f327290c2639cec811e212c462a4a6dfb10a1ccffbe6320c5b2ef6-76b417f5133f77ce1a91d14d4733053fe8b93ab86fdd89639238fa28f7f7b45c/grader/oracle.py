"""Independent grouping facts for historical receipts; complete schedule products."""
from itertools import product,combinations


def transform(bundle):
    s=bundle['schedule'];l=bundle['ledger'];c={x['id']:x for x in s['credentials']};slots=sorted(s['slots'])
    if len(c)!=len(s['credentials']) or len({r['id'] for r in s['routes']})!=len(s['routes']):raise ValueError('duplicate authority ID')
    def records(rows):
        result={}
        for name in {r['id'] for r in rows}:
            matching=[r for r in rows if r['id']==name]
            if any(r!=matching[0] for r in matching):raise ValueError('conflicting record ID')
            result[name]=matching[0]
        return result
    attempts=records(l['attempts']);receipts=records(l['receipts'])
    for row in c.values():
        if row['pool'] not in s['budgets'] or row['parent'] is not None and row['parent'] not in c:raise ValueError('unknown credential edge')
    for chain in [r['credentials'] for r in s['routes']]+[a['credentials'] for a in attempts.values()]:
        if not set(chain)<=set(c):raise ValueError('unknown chain node')
    declared={r['reservation'] for r in receipts.values() if r['kind']=='reserve'}
    for row in receipts.values():
        if row['kind'] in ('reserve','reject') and row['attempt'] not in attempts:raise ValueError('unknown attempt')
        if row['kind'] in ('commit','release') and row['reservation'] not in declared:raise ValueError('unknown reservation')
    visible=[r for r in receipts.values() if r['at']<=s['as_of']]
    for r in visible:
        if r['kind'] in ('reserve','reject') and attempts[r['attempt']]['at']>r['at']:raise ValueError('receipt predates attempt')
    resolved={};key_owners={}
    for name in sorted({r['reservation'] for r in visible if r['kind']!='reject'}):
        rows=[r for r in visible if r.get('reservation')==name]
        reservations=[r for r in rows if r['kind']=='reserve']
        if not reservations:raise ValueError('no visible binding')
        first=min(reservations,key=lambda r:(r['at'],r['id']))
        a=attempts[first['attempt']]
        bindings={(r['attempt'],r['expires']) for r in reservations}
        if len(bindings)!=1 or first['expires']<=first['at']:raise ValueError('conflicting or expired binding')
        if a['key'] in key_owners:raise ValueError('one key bound twice')
        key_owners[a['key']]=name
        terminals=[r for r in rows if r['kind'] in ('commit','release')]
        if any((r['at'],r['id'])<(first['at'],first['id']) for r in terminals):raise ValueError('terminal before reserve')
        kinds={r['kind'] for r in terminals}
        if len(kinds)>1:raise ValueError('contradictory terminal facts')
        if 'commit' in kinds and min(r['at'] for r in terminals)>=first['expires']:raise ValueError('expired commit')
        state='committed' if 'commit' in kinds else 'released' if 'release' in kinds else 'expired' if first['expires']<=s['as_of'] else 'held'
        resolved[name]={'key':a['key'],'attempt':a['id'],'units':a['units'],'pools':sorted({c[n]['pool'] for n in a['credentials']}),'expires':first['expires'],'state':state}
    availability={p:{str(t):s['budgets'][p]-sum(v['units'] for v in resolved.values() if p in v['pools'] and (v['state']=='committed' or v['state']=='held' and t<v['expires'])) for t in slots} for p in sorted(s['budgets'])}
    requests=sorted(s['requests'],key=lambda q:q['id']);options={q['id']:[] for q in requests}
    for q in requests:
        for r in sorted(s['routes'],key=lambda x:x['id']):
            if r['request']!=q['id']:continue
            names=r['credentials']
            structurally_valid=bool(names) and c[names[0]]['parent'] is None and names[-1] in q['leaves'] and all(c[names[i]]['parent']==names[i-1] for i in range(1,len(names)))
            if not structurally_valid or any(not set(q['scopes'])<=set(c[n]['scopes']) for n in names):continue
            for t in slots:
                if q['earliest']<=t and t+q['duration']<=q['latest'] and all(c[n]['start']<=t and t+q['duration']<=c[n]['end'] for n in names):options[q['id']].append({'route':r['id'],'slot':t,'pools':sorted({c[n]['pool'] for n in names})})
    def solve(qs,props=()):
        allowances={p:{t:v+sum(z['units'] for z in props if z['kind']=='budget' and z['pool']==p) for t,v in row.items()} for p,row in availability.items()}
        capacity={str(t):s['workers'][str(t)]+sum(p['units'] for p in props if p['kind']=='worker' and p['slot']==t) for t in slots}
        for choices in product(*(options[q['id']] for q in qs)):
            if any(sum(q['units'] for q,o in zip(qs,choices) if o['slot']==t)>capacity[str(t)] for t in slots):continue
            if any(sum(q['units'] for q,o in zip(qs,choices) if p in o['pools'] and o['slot']<=t)>allowances[p][str(t)] for p in allowances for t in slots):continue
            return {q['id']:{'route':o['route'],'slot':o['slot']} for q,o in zip(qs,choices)}
        return None
    assignment=solve(requests)
    cores=[[q['id'] for q in selected] for n in range(1,len(requests)+1) for selected in combinations(requests,n) if assignment is None and solve(selected) is None]
    proposals=sorted(bundle['proposals'],key=lambda p:p['id']);repairs=[]
    for bits in product((False,True),repeat=len(proposals)):
        selected=[p for p,chosen in zip(proposals,bits) if chosen];answer=solve(requests,selected)
        if answer is not None:
            ids=[p['id'] for p in selected];cost=sum(p['cost'] for p in selected)
            repairs.append((cost,len(ids),ids,{'proposal_ids':ids,'cost':cost,'assignment':answer}))
    return {'ready':assignment is not None,'reservation_state':resolved,'availability':availability,'route_options':options,'assignment':assignment,'obstruction':min(cores,key=lambda x:(len(x),x)) if cores else [],'owner_request':min(repairs,key=lambda x:x[:3])[3] if repairs else None,'blocker_codes':[] if assignment is not None else ['batch_delegation_budget_required']}
