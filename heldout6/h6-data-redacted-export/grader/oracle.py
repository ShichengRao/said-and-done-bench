"""Independent literal old/current pairs and complete public policy tables."""
import itertools


def transform(bundle):
    roster=bundle['roster'];names=sorted(roster['people']);position={name:i for i,name in enumerate(names)};n=len(names)
    targets={}
    for link in roster['aliases']:
        targets.setdefault(link['alias'],set()).add(link['target'])
    if any(len(values)!=1 for values in targets.values()):raise ValueError('alias conflict')
    def resolve(name):
        visited=set()
        while name not in position:
            if name in visited or name not in targets:raise ValueError('alias/member reference')
            visited.add(name);name=next(iter(targets[name]))
        return position[name]
    for name in targets:resolve(name)
    def members(row):return tuple(sorted({resolve(name) for name in row['members']}))
    priors=[(row['epoch'],members(row),row['count']) for row in bundle['prior']]
    snapshots={epoch:tuple(bundle['snapshots'][epoch][name] for name in names) for epoch in ('old','current')}
    if any(sum(snapshots[epoch][i] for i in cohort)!=value for epoch,cohort,value in priors):raise ValueError('published evidence contradiction')
    bound=bundle['policy']['max_changes']
    if sum(a!=b for a,b in zip(snapshots['old'],snapshots['current']))>bound:raise ValueError('transition contradiction')
    vectors=list(itertools.product((0,1),repeat=n));projected=set()
    for old in vectors:
        for current in vectors:
            if sum(a!=b for a,b in zip(old,current))>bound:continue
            if all(sum((old if epoch=='old' else current)[i] for i in cohort)==value for epoch,cohort,value in priors):projected.add(current)
    key=lambda vector:sum(value*2**i for i,value in enumerate(vector))
    worlds=sorted(projected,key=key)
    if len(worlds)>12:raise ValueError('projected world bound exceeded')
    protected=[position[name] for name in bundle['policy']['protected']]
    def ambiguity(vectors):return sum({vector[i] for vector in vectors}=={0,1} for i in protected)
    baseline_safe=bool(worlds) and ambiguity(worlds)==len(protected)
    approvals={}
    for person in names:
        rows=[row for row in roster['consents'] if row['person']==person]
        approvals[position[person]]=max(rows,key=lambda row:row['revision'])['allowed'] if rows else False
    packages=[];excluded=[]
    for row in sorted(bundle['packages'],key=lambda p:p['id']):
        queries=sorted((query['id'],members(query)) for query in row['queries'])
        permitted=row['approved'] and all(approvals[i] for _,cohort in queries for i in cohort)
        if not permitted:excluded.append({'id':row['id'],'reason':'not_authorized'})
        elif row['utility']<bundle['policy']['minimum_utility']:excluded.append({'id':row['id'],'reason':'below_utility_floor'})
        else:packages.append(dict(id=row['id'],utility=row['utility'],queries=queries))
    signatures=[[(k,tuple(sum(world[i] for i in cohort) for _,cohort in package['queries'])) for world in worlds] for k,package in enumerate(packages)]
    safe_groups=[False]*(1<<len(worlds))
    for mask in range(1,len(safe_groups)):
        safe_groups[mask]=ambiguity([world for i,world in enumerate(worlds) if mask>>i&1])==len(protected)
    winner=None;score=-1
    if baseline_safe:
        for table in itertools.product(range(len(packages)),repeat=len(worlds)):
            value=sum(packages[k]['utility'] for k in table)
            if value<score:continue
            groups={}
            for i,k in enumerate(table):
                signature=signatures[k][i];groups[signature]=groups.get(signature,0)|(1<<i)
            if not all(safe_groups[group] for group in groups.values()):continue
            if value>score or winner is None or table<winner:winner=table;score=value
    decision=None;publication=None;total=None;guarantee=None;remaining=worlds
    if winner is not None:
        decision=[{'world':key(world),'package':packages[k]['id']} for world,k in zip(worlds,winner)]
        total=score;guarantee=min(packages[k]['utility'] for k in winner)
        chosen=winner[worlds.index(snapshots['current'])];package=packages[chosen]
        signature=signatures[chosen][worlds.index(snapshots['current'])]
        remaining=[world for i,(world,k) in enumerate(zip(worlds,winner)) if signatures[k][i]==signature]
        publication={'package':package['id'],'counts':[{'id':name,'count':value} for (name,_),value in zip(package['queries'],signature[1])],'utility':package['utility']}
    ready=winner is not None
    return {'ready':ready,'baseline_safe':baseline_safe,'baseline_candidate_count':len(worlds),'policy':decision,'total_utility':total,'guaranteed_utility':guarantee,'publication':publication,'candidate_count':len(remaining),'protected_count':len(protected),'ambiguous_protected_count':ambiguity(remaining),'excluded_packages':excluded,'blocker_codes':[] if ready else ['prior_release_privacy_conflict'] if not baseline_safe else ['privacy_policy_floor_unreachable']}
