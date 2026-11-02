"""Independent old/current-pair enumeration and projection before count inference."""
from itertools import product


def transform(bundle):
    roster=bundle['roster'];people=sorted(roster['people']);number=len(people)
    aliases={}
    for row in roster['aliases']:
        a=row['alias']
        if a in aliases and aliases[a]!=row['target']:raise ValueError('alias conflict')
        aliases[a]=row['target']
    def canonical(name):
        visited=set()
        while name not in people:
            if name not in aliases or name in visited:raise ValueError('invalid alias chain')
            visited.add(name);name=aliases[name]
        return name
    for a in aliases:canonical(a)
    memberships={row['id']:sorted({people.index(canonical(name)) for name in row['members']}) for row in bundle['prior']+bundle['queries']}
    actual={epoch:tuple(bundle['snapshots'][epoch][name] for name in people) for epoch in ('old','current')}
    def value(vector,query):return sum(vector[i] for i in memberships[query['id']])
    limit=bundle['policy']['max_changes']
    if sum(a!=c for a,c in zip(actual['old'],actual['current']))>limit or any(value(actual[q['epoch']],q)!=q['count'] for q in bundle['prior']):raise ValueError('inconsistent snapshots')
    worlds=list(product((0,1),repeat=number))
    old_worlds=[w for w in worlds if all(value(w,q)==q['count'] for q in bundle['prior'] if q['epoch']=='old')]
    current_worlds=[w for w in worlds if all(value(w,q)==q['count'] for q in bundle['prior'] if q['epoch']=='current')]
    pairs=[(a,c) for a in old_worlds for c in current_worlds if sum(x!=y for x,y in zip(a,c))<=limit]
    projected=set(c for a,c in pairs)
    protected=[people.index(p) for p in bundle['policy']['protected']]
    def ambiguous(vs):return sum({v[i] for v in vs}=={0,1} for i in protected)
    def safe(vs):return bool(vs) and ambiguous(vs)==len(protected)
    def count_candidates(selected):return {v for v in projected if all(value(v,q)==value(actual['current'],q) for q in selected)}
    consent={p:False for p in people}
    for p in people:
        records=[r for r in roster['consents'] if r['person']==p]
        if records:consent[p]=max(records,key=lambda r:r['revision'])['allowed']
    queries=sorted(bundle['queries'],key=lambda q:q['id'])
    eligible={q['id']:q['approved'] and all(consent[people[i]] for i in memberships[q['id']]) for q in queries}
    baseline_safe=safe(projected);good=[]
    for bits in product((0,1),repeat=len(queries)):
        subset=[q for q,bit in zip(queries,bits) if bit]
        if not baseline_safe or any(not eligible[q['id']] for q in subset):continue
        if safe(count_candidates(subset)):good.append((-sum(q['utility'] for q in subset),-len(subset),[q['id'] for q in subset],subset))
    selected=min(good,key=lambda row:row[:3])[3] if good else []
    ids=[q['id'] for q in selected];utility=sum(q['utility'] for q in selected);posterior=count_candidates(selected)
    ready=baseline_safe and utility>=bundle['policy']['minimum_utility']
    return {'ready':ready,'baseline_safe':baseline_safe,'selected':ids,'utility':utility,'publication':[{'id':q['id'],'count':value(actual['current'],q),'utility':q['utility']} for q in selected],'suppressed':[{'id':q['id'],'reason':'not_authorized' if not eligible[q['id']] else 'prior_privacy_conflict' if not baseline_safe else 'cumulative_privacy'} for q in queries if q['id'] not in ids],'baseline_candidate_count':len(projected),'candidate_count':len(posterior),'protected_count':len(protected),'ambiguous_protected_count':ambiguous(posterior),'blocker_codes':[] if ready else ['prior_release_privacy_conflict'] if not baseline_safe else ['privacy_utility_floor_unreachable']}
