"""Independent oracle enumerates complete route/start products before charging pools."""
from itertools import product,combinations

def transform(b):
    s=b['schedule'];cs={c['id']:c for c in s['credentials']};qs=sorted(s['requests'],key=lambda q:q['id']);rs=sorted(s['routes'],key=lambda r:r['id'])
    if len(cs)!=len(s['credentials']) or len({r['id'] for r in rs})!=len(rs):raise ValueError('duplicate identity')
    if any(c not in cs for r in rs for c in r['credentials']):raise ValueError('unknown credential')
    opts={}
    for q in qs:
        opts[q['id']]=[]
        for r in rs:
            if r['request']!=q['id'] or not r['credentials']:continue
            names=r['credentials'];valid=cs[names[0]]['parent'] is None and names[-1] in q['leaves']
            for i,name in enumerate(names):
                c=cs[name]
                valid &= all(scope in c['scopes'] for scope in q['scopes'])
                if i:valid &= c['parent']==names[i-1]
            if not valid:continue
            pools=sorted(set(cs[n]['pool'] for n in names))
            for t in sorted(s['slots']):
                if not q['earliest']<=t or t+q['duration']>q['latest']:continue
                if not all(cs[n]['start']<=t and t+q['duration']<=cs[n]['end'] for n in names):continue
                opts[q['id']].append({'route':r['id'],'slot':t,'pools':pools})
    def witness(rows,props=()):
        budgets=dict(s['budgets']);workers=dict(s['workers'])
        for p in props:
            if p['kind']=='budget':budgets[p['pool']]+=p['units']
            else:workers[str(p['slot'])]+=p['units']
        for selection in product(*(opts[q['id']] for q in rows)):
            if any(sum(q['units'] for q,o in zip(rows,selection) if p in o['pools'])>limit for p,limit in budgets.items()):continue
            if any(sum(q['units'] for q,o in zip(rows,selection) if str(o['slot'])==slot)>limit for slot,limit in workers.items()):continue
            return {q['id']:{'route':o['route'],'slot':o['slot']} for q,o in zip(rows,selection)}
        return None
    assignment=witness(qs);core=[]
    if assignment is None:
        candidates=[]
        for bits in product([0,1],repeat=len(qs)):
            rows=[q for q,k in zip(qs,bits) if k]
            if rows and witness(rows) is None:candidates.append([q['id'] for q in rows])
        core=min(candidates,key=lambda x:(len(x),x))
    props=sorted(b['proposals'],key=lambda p:p['id']);fixes=[]
    for bits in product([0,1],repeat=len(props)):
        chosen=[p for p,k in zip(props,bits) if k];w=witness(qs,chosen)
        if w is not None:fixes.append((sum(p['cost'] for p in chosen),len(chosen),[p['id'] for p in chosen],w))
    fix=min(fixes,key=lambda x:x[:3]) if fixes else None
    return {'ready':assignment is not None,'route_options':opts,'assignment':assignment,'obstruction':core,'owner_request':{'proposal_ids':fix[2],'cost':fix[0],'assignment':fix[3]} if fix else None,'blocker_codes':[] if assignment is not None else ['batch_delegation_budget_required']}
