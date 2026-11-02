"""Independent oracle refines explicit set partitions and exhausts query masks."""
from itertools import product

def transform(b):
    roster=b['roster'];universe=set(roster['people']);links={}
    for row in roster['aliases']:
        if row['alias'] in links and links[row['alias']]!=row['target']:raise ValueError('alias conflict')
        links[row['alias']]=row['target']
    mapping={p:p for p in universe}
    for alias in links:
        visited=set();cur=alias
        while cur not in universe:
            if cur in visited or cur not in links:raise ValueError('alias cycle or missing target')
            visited.add(cur);cur=links[cur]
        mapping[alias]=cur
    consent={}
    for row in sorted(roster['consents'],key=lambda x:x['revision']):consent[row['person']]=row['allowed']
    prior=sorted(b['prior'],key=lambda q:q['id']);queries=sorted(b['queries'],key=lambda q:q['id']);cohorts={}
    for q in prior+queries:
        if any(n not in mapping for n in q['members']):raise ValueError('unknown member')
        cohorts[q['id']]=set(mapping[n] for n in q['members'])
    eligible=[q for q in queries if q['approved'] and all(consent.get(p,False) for p in cohorts[q['id']])]
    def parts(selected):
        partition=[universe] if universe else []
        for q in prior+selected:
            group=cohorts[q['id']];updated=[]
            for cell in partition:
                for piece in [cell&group,cell-group]:
                    if piece:updated.append(piece)
            partition=updated
        return sorted(len(cell) for cell in partition)
    baseline=all(n>=b['policy']['k'] for n in parts([]));candidates=[]
    if baseline:
        for bits in product([0,1],repeat=len(eligible)):
            chosen=[q for q,k in zip(eligible,bits) if k]
            if all(n>=b['policy']['k'] for n in parts(chosen)):candidates.append((-sum(q['utility'] for q in chosen),-len(chosen),[q['id'] for q in chosen],chosen))
    best=min(candidates,key=lambda x:x[:3])[3] if candidates else [];ids=[q['id'] for q in best];allowed={q['id'] for q in eligible};score=sum(q['utility'] for q in best);ready=baseline and score>=b['policy']['minimum_utility']
    return {'ready':ready,'baseline_safe':baseline,'selected':ids,'utility':score,'publication':[{'id':q['id'],'count':len(cohorts[q['id']]),'utility':q['utility']} for q in best],'suppressed':[{'id':q['id'],'reason':'not_authorized' if q['id'] not in allowed else 'prior_privacy_conflict' if not baseline else 'cumulative_privacy'} for q in queries if q['id'] not in ids],'atom_sizes':parts(best),'blocker_codes':[] if ready else ['prior_release_privacy_conflict'] if not baseline else ['privacy_utility_floor_unreachable']}
