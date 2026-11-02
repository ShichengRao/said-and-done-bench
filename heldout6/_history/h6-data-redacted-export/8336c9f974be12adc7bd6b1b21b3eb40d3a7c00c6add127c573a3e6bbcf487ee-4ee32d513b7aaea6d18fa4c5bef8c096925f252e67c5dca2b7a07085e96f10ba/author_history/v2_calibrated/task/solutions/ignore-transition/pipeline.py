from itertools import combinations


def transform(bundle):
    roster=bundle['roster'];people=sorted(roster['people']);index={p:i for i,p in enumerate(people)};n=len(people);policy=bundle['policy']
    links={}
    for a in roster['aliases']:
        if a['alias'] in links and links[a['alias']]!=a['target']:raise ValueError('conflicting alias')
        links[a['alias']]=a['target']
    def resolve(name,path=()):
        if name in index:return name
        if name in path or name not in links:raise ValueError('cyclic or unknown identity')
        return resolve(links[name],path+(name,))
    for name in links:resolve(name)
    def cohort(row):return sum(1<<index[p] for p in {resolve(x) for x in row['members']})
    prior=[(row['epoch'],cohort(row),row['count']) for row in bundle['prior']]
    consent={}
    for row in roster['consents']:
        if row['person'] not in consent or row['revision']>consent[row['person']]['revision']:consent[row['person']]=row
    truth={epoch:sum(bundle['snapshots'][epoch][p]<<index[p] for p in people) for epoch in ('old','current')}
    if (truth['old']^truth['current']).bit_count()>policy['max_changes'] or any((truth[epoch]&mask).bit_count()!=count for epoch,mask,count in prior):raise ValueError('private snapshot contradicts public evidence')
    protected=[index[p] for p in policy['protected']]
    old_rows=[(mask,count) for epoch,mask,count in prior if epoch=='old']
    current_rows=[(mask,count) for epoch,mask,count in prior if epoch=='current']
    old_vectors=[v for v in range(1<<n) if all((v&mask).bit_count()==count for mask,count in old_rows)]
    states=[v for v in range(1<<n) if all((v&mask).bit_count()==count for mask,count in current_rows) and min(((v^old).bit_count() for old in old_vectors),default=n+1)<=n]
    queries=[]
    for row in sorted(bundle['queries'],key=lambda q:q['id']):
        mask=cohort(row);authorized=row['approved'] and all(consent.get(people[i],{}).get('allowed',False) for i in range(n) if mask>>i&1)
        queries.append({'id':row['id'],'mask':mask,'utility':row['utility'],'count':(truth['current']&mask).bit_count(),'authorized':authorized})
    def surviving(selected):return [v for v in states if all((v&q['mask']).bit_count()==q['count'] for q in selected)]
    def ambiguous(vs):return sum(any(v>>i&1 for v in vs) and any(not(v>>i&1) for v in vs) for i in protected)
    def safe(vs):return bool(vs) and ambiguous(vs)==len(protected)
    baseline_safe=safe(states);authorized=[q for q in queries if q['authorized']]
    chosen=[]
    if baseline_safe:
        candidates=[]
        for count in range(len(authorized)+1):
            for subset in combinations(authorized,count):
                if safe(surviving(subset)):candidates.append((-sum(q['utility'] for q in subset),-len(subset),[q['id'] for q in subset],subset))
        chosen=list(min(candidates,key=lambda x:x[:3])[3])
    selected=[q['id'] for q in chosen];utility=sum(q['utility'] for q in chosen);posterior=surviving(chosen)
    ready=baseline_safe and utility>=policy['minimum_utility']
    codes=[] if ready else ['prior_release_privacy_conflict'] if not baseline_safe else ['privacy_utility_floor_unreachable']
    return {'ready':ready,'baseline_safe':baseline_safe,'selected':selected,'utility':utility,'publication':[{'id':q['id'],'count':q['count'],'utility':q['utility']} for q in chosen],'suppressed':[{'id':q['id'],'reason':'not_authorized' if not q['authorized'] else 'prior_privacy_conflict' if not baseline_safe else 'cumulative_privacy'} for q in queries if q['id'] not in selected],'baseline_candidate_count':len(states),'candidate_count':len(posterior),'protected_count':len(protected),'ambiguous_protected_count':ambiguous(posterior),'blocker_codes':codes}

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
