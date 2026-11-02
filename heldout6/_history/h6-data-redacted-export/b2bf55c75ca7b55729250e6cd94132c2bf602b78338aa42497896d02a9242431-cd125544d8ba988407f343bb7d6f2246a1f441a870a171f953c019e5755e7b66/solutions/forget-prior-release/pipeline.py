from itertools import combinations

def transform(bundle):
    roster=bundle['roster'];people=set(roster['people']);links={};cache={}
    for row in roster['aliases']:
        if row['alias'] in links and links[row['alias']]!=row['target']:raise ValueError('conflicting alias')
        links[row['alias']]=row['target']
    def resolve(name,trail=frozenset()):
        if name in people:return name
        if name in cache:return cache[name]
        if name in trail or name not in links:raise ValueError('invalid alias chain')
        result=resolve(links[name],trail|{name});cache[name]=result;return result
    for name in links:resolve(name)
    consent={}
    for row in roster['consents']:
        if row['person'] not in consent or row['revision']>consent[row['person']]['revision']:consent[row['person']]=row
    queries=sorted(bundle['queries'],key=lambda q:q['id']);prior=sorted(bundle['prior'],key=lambda q:q['id']);members={q['id']:{resolve(n) for n in q['members']} for q in prior+queries}
    eligible=[q for q in queries if q['approved'] and all(consent.get(p,{}).get('allowed',False) for p in members[q['id']])]
    def atoms(chosen):
        cohorts=[members[q['id']] for q in chosen];sizes={}
        for p in people:
            signature=tuple(p in c for c in cohorts);sizes[signature]=sizes.get(signature,0)+1
        return sorted(sizes.values())
    def safe(chosen):return all(n>=bundle['policy']['k'] for n in atoms(chosen))
    baseline=safe([]);best=[];best_key=(0,0,[])
    if baseline:
        for n in range(len(eligible)+1):
            for chosen in combinations(eligible,n):
                if not safe(list(chosen)):continue
                key=(-sum(q['utility'] for q in chosen),-len(chosen),[q['id'] for q in chosen])
                if key<best_key:best_key=key;best=list(chosen)
    selected={q['id'] for q in best};allowed={q['id'] for q in eligible};utility=sum(q['utility'] for q in best)
    ready=baseline and utility>=bundle['policy']['minimum_utility']
    codes=[] if ready else ['prior_release_privacy_conflict'] if not baseline else ['privacy_utility_floor_unreachable']
    return {'ready':ready,'baseline_safe':baseline,'selected':[q['id'] for q in best],'utility':utility,'publication':[{'id':q['id'],'count':len(members[q['id']]),'utility':q['utility']} for q in best],'suppressed':[{'id':q['id'],'reason':'not_authorized' if q['id'] not in allowed else 'prior_privacy_conflict' if not baseline else 'cumulative_privacy'} for q in queries if q['id'] not in selected],'atom_sizes':atoms(best),'blocker_codes':codes}

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
