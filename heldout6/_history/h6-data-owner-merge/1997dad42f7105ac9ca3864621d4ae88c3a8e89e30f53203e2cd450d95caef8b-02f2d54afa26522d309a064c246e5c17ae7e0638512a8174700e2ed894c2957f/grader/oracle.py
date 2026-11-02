from copy import deepcopy

def reconstruct(h):
    rows=h['entries'];identities=[(r['kind'],r['entity'],r['revision']) for r in rows]
    if len(identities)!=len(set(identities)):raise ValueError('duplicate revision')
    def snapshot(kind,phase):
        result={}
        candidates=sorted((r for r in rows if r['kind']==kind and r['approved'] and r['effective']<=phase and r['recorded']<=h['cutoff']),key=lambda r:r['revision'])
        for row in candidates:result[row['entity']]=row['value']
        return result
    names=sorted(snapshot('record',0));adj={n:set() for n in names}
    for merge in snapshot('merge',0).values():
        if merge['active']:adj[merge['left']].add(merge['right']);adj[merge['right']].add(merge['left'])
    unseen=set(names);parts=[]
    while unseen:
        stack=[min(unseen)];members=set()
        while stack:
            node=stack.pop()
            if node not in members:members.add(node);stack.extend(adj[node]-members)
        unseen-=members;parts.append(sorted(members))
    groups=[]
    for members in sorted(parts):
        loads=[];owners=[];handoffs=[]
        for k in range(h['phases']):
            state=snapshot('record',k);loads.append(sum(state[n]['units'] for n in members));pool=set(o for n in members for o in state[n]['owners']);owners.append(sorted(o for o in pool if all(o in state[n]['owners'] for n in members)))
            if k<h['phases']-1:
                for grant in snapshot('handoff',k).values():
                    if grant['record'] in members and grant['boundary']==k and grant['active']:handoffs.append([k,grant['from'],grant['to']])
        groups.append({'id':members[0],'members':members,'load':loads,'allowed':owners,'handoffs':sorted(handoffs)})
    phases=[snapshot('capacity',k) for k in range(h['phases'])];capacity={n:[phase[n]['units'] for phase in phases] for n in phases[0]}
    return {'phases':h['phases'],'capacity':capacity,'groups':groups}
"""Independent finite oracle: enumerate complete owner matrices, then filter rules."""
from itertools import product,combinations
from copy import deepcopy

def plan_transform(b):
    p=b['plan'];groups=sorted(p['groups'],key=lambda x:x['id']);names=[g['id'] for g in groups];owners=sorted(p['capacity']);phases=p['phases']
    if len(names)!=len(set(names)):raise ValueError('duplicate group')
    if any(o not in owners for g in groups for row in g['allowed'] for o in row):raise ValueError('unknown owner')
    def context(props):
        caps=deepcopy(p['capacity']);edges={g['id']:list(g['handoffs']) for g in groups}
        for prop in props:
            if prop['kind']=='capacity':caps[prop['owner']][prop['phase']]+=prop['units']
            else:edges[prop['group']].append([prop['phase'],prop['from'],prop['to']])
        choices={}
        for g in groups:
            choices[g['id']]=[]
            for vector in product(owners,repeat=phases):
                if any(o not in g['allowed'][i] for i,o in enumerate(vector)):continue
                if any(vector[i]!=vector[i+1] and [i,vector[i],vector[i+1]] not in edges[g['id']] for i in range(phases-1)):continue
                choices[g['id']].append(list(vector))
        return caps,choices
    def feasible(subset,props=()):
        caps,choices=context(props)
        for matrix in product(*(choices[g['id']] for g in subset)):
            if all(sum(g['load'][k] for g,path in zip(subset,matrix) if path[k]==owner)<=caps[owner][k] for k in range(phases) for owner in owners):return {g['id']:path for g,path in zip(subset,matrix)}
        return None
    _,paths=context([]);assignment=feasible(groups);per_phase=[]
    for k in range(phases):
        candidates=[]
        for row in product(owners,repeat=len(groups)):
            if any(row[i] not in g['allowed'][k] for i,g in enumerate(groups)):continue
            if any(sum(g['load'][k] for g,o in zip(groups,row) if o==owner)>p['capacity'][owner][k] for owner in owners):continue
            candidates.append(dict(zip(names,row)))
        per_phase.append(candidates[0] if candidates else None)
    cores=[list(subset) for n in range(1,len(groups)+1) for subset in combinations(names,n) if assignment is None and feasible([g for g in groups if g['id'] in subset]) is None]
    props=sorted(b['proposals'],key=lambda x:x['id']);requests=[]
    for bits in product([0,1],repeat=len(props)):
        chosen=[p for p,k in zip(props,bits) if k];witness=feasible(groups,chosen)
        if witness is not None:
            ids=[p['id'] for p in chosen];cost=sum(p['cost'] for p in chosen)
            requests.append((cost,len(ids),ids,{'proposal_ids':ids,'cost':cost,'assignment':witness}))
    return {'ready':assignment is not None,'local_paths':paths,'phase_witnesses':per_phase,'assignment':assignment,'obstruction':min(cores,key=lambda x:(len(x),x)) if cores else [],'owner_request':min(requests,key=lambda x:x[:3])[3] if requests else None,'blocker_codes':[] if assignment is not None else ['joint_stewardship_authority_required']}

def transform(bundle):
    plan=reconstruct(bundle['history'])
    result=plan_transform({'plan':plan,'proposals':bundle['proposals']})
    result['resolved_plan']=plan
    return result
