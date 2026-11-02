"""Independent finite oracle: enumerate complete owner matrices, then filter rules."""
from itertools import product,combinations
from copy import deepcopy

def transform(b):
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
