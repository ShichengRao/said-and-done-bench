"""Independent oracle filters full placement products with a scenario matrix."""
from itertools import product,combinations
from copy import deepcopy

def transform(b):
    p=b['placement'];nodes={n['id']:n for n in p['nodes']};templates={t['id']:t['nodes'] for t in p['templates']};ds=sorted(p['datasets'],key=lambda x:x['id']);ss=sorted(p['scenarios'],key=lambda x:x['id'])
    if len(nodes)!=len(p['nodes']) or len(templates)!=len(p['templates']) or len({d['id'] for d in ds})!=len(ds):raise ValueError('duplicate identity')
    if any(t not in templates for d in ds for t in d['templates']):raise ValueError('unknown template')
    eligible={}
    for d in ds:
        eligible[d['id']]=[]
        for t in sorted(set(d['templates'])):
            if any(nodes[n]['region'] not in d['regions'] or d['key'] not in nodes[n]['keys'] for n in templates[t]):continue
            eligible[d['id']].append(t)
    def allowed(selection,rows,scenarios,props):
        limits={s['id']:dict(s['capacity']) for s in scenarios}
        for q in props:
            if q['scenario'] in limits:limits[q['scenario']][q['node']]+=q['units']
        for scenario in scenarios:
            for d,t in zip(rows,selection):
                if len(set(templates[t])-set(scenario['down']))<d['survivors']:return False
            for node in nodes:
                if node in scenario['down']:continue
                total=sum(d['units'] for d,t in zip(rows,selection) if node in templates[t])
                if total>limits[scenario['id']][node]:return False
        return True
    def first(rows,scenarios,props=()):
        for selection in product(*(eligible[d['id']] for d in rows)):
            if allowed(selection,rows,scenarios,props):return {d['id']:t for d,t in zip(rows,selection)}
        return None
    assignment=first(ds,ss)
    robust={d['id']:[t for t in eligible[d['id']] if allowed([t],[d],ss,[])] for d in ds}
    witnesses={s['id']:first(ds,[s]) for s in ss};cores=[]
    if assignment is None:
        for dbits in product([0,1],repeat=len(ds)):
            rows=[d for d,k in zip(ds,dbits) if k]
            if not rows:continue
            for sbits in product([0,1],repeat=len(ss)):
                scs=[s for s,k in zip(ss,sbits) if k]
                if not scs or first(rows,scs) is not None:continue
                dn=[d['id'] for d in rows];sn=[s['id'] for s in scs];cores.append((len(dn)+len(sn),len(dn),dn,sn))
    c=min(cores) if cores else None
    requests=[];props=sorted(b['proposals'],key=lambda x:x['id'])
    for bits in product([0,1],repeat=len(props)):
        chosen=[q for q,k in zip(props,bits) if k];answer=first(ds,ss,chosen)
        if answer is not None:
            ids=[q['id'] for q in chosen];cost=sum(q['cost'] for q in chosen);requests.append((cost,len(ids),ids,answer))
    req=min(requests,key=lambda x:x[:3]) if requests else None
    return {'ready':assignment is not None,'eligible_templates':eligible,'robust_options':robust,'scenario_witnesses':witnesses,'assignment':assignment,'obstruction':{'datasets':c[2],'scenarios':c[3]} if c else None,'owner_request':{'proposal_ids':req[2],'cost':req[0],'assignment':req[3]} if req else None,'blocker_codes':[] if assignment is not None else ['robust_placement_authority_required']}
