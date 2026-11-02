from functools import lru_cache

MODE='local-selection'


def compile_policy(worlds,packages,protected_mask):
    """Cover worlds by ambiguous equal-answer cells; merged equal cells stay safe."""
    count=len(worlds);full=(1<<count)-1
    union=[0]*(1<<count);common=[31]*(1<<count);safe=[False]*(1<<count)
    for mask in range(1,1<<count):
        bit=mask&-mask;i=bit.bit_length()-1;rest=mask^bit
        union[mask]=union[rest]|worlds[i];common[mask]=common[rest]&worlds[i]
        safe[mask]=((union[mask]^common[mask])&protected_mask)==protected_mask
    fibers=[]
    for package in packages:
        groups={}
        for i,world in enumerate(worlds):
            answer=tuple((world&mask).bit_count() for _,mask in package['queries'])
            groups[answer]=groups.get(answer,0)|(1<<i)
        fibers.append([next(group for group in groups.values() if group>>i&1) for i in range(count)])
    if MODE=='local-selection':
        chosen=[]
        for i in range(count):
            options=[k for k in range(len(packages)) if safe[fibers[k][i]]]
            if not options:return None
            chosen.append(min(options,key=lambda k:(-packages[k]['utility'],packages[k]['id'])))
        return tuple(chosen)
    if MODE=='static-only':
        possible=[k for k in range(len(packages)) if all(safe[group] for group in set(fibers[k]))]
        if not possible:return None
        best=min(possible,key=lambda k:(-packages[k]['utility'],packages[k]['id']))
        return (best,)*count
    @lru_cache(None)
    def cover(remaining):
        if not remaining:return (0,(-1,)*count)
        first=(remaining&-remaining).bit_length()-1;best=None
        for k,package in enumerate(packages):
            available=fibers[k][first]&remaining;subset=available
            while subset:
                if subset>>first&1 and safe[subset]:
                    child=cover(remaining^subset)
                    if child is not None:
                        table=list(child[1])
                        for i in range(count):
                            if subset>>i&1:table[i]=k
                        result=(child[0]+subset.bit_count()*package['utility'],tuple(table))
                        if best is None or result[0]>best[0] or result[0]==best[0] and result[1]<best[1]:best=result
                subset=(subset-1)&available
        return best
    result=cover(full)
    return None if result is None else result[1]


def transform(bundle):
    roster=bundle['roster'];people=sorted(roster['people']);index={p:i for i,p in enumerate(people)};n=len(people);policy=bundle['policy']
    links={}
    for row in roster['aliases']:
        if row['alias'] in links and links[row['alias']]!=row['target']:raise ValueError('conflicting alias')
        links[row['alias']]=row['target']
    def resolve(name,path=()):
        if name in index:return name
        if name in path or name not in links:raise ValueError('invalid alias/member')
        return resolve(links[name],path+(name,))
    for name in links:resolve(name)
    def cohort(members):return sum(1<<index[p] for p in {resolve(name) for name in members})
    prior=[(row['epoch'],cohort(row['members']),row['count']) for row in bundle['prior']]
    consent={}
    for row in roster['consents']:
        if row['person'] not in consent or row['revision']>consent[row['person']]['revision']:consent[row['person']]=row
    truth={epoch:sum(bundle['snapshots'][epoch][p]<<index[p] for p in people) for epoch in ('old','current')}
    if (truth['old']^truth['current']).bit_count()>policy['max_changes'] or any((truth[epoch]&mask).bit_count()!=count for epoch,mask,count in prior):raise ValueError('private snapshots contradict public evidence')
    old_rows=[(mask,count) for epoch,mask,count in prior if epoch=='old'];current_rows=[(mask,count) for epoch,mask,count in prior if epoch=='current']
    if MODE=='drop-old-publications':old_rows=[]
    old=[v for v in range(1<<n) if all((v&mask).bit_count()==count for mask,count in old_rows)]
    if MODE=='condition-on-private-old':old=[truth['old']]
    limit=n if MODE=='ignore-transition' else policy['max_changes']
    worlds=[v for v in range(1<<n) if all((v&mask).bit_count()==count for mask,count in current_rows) and min(((v^o).bit_count() for o in old),default=n+1)<=limit]
    if len(worlds)>12:raise ValueError('projected world bound exceeded')
    protected_mask=sum(1<<index[p] for p in policy['protected'])
    def ambiguity(values):return sum(any(v>>i&1 for v in values) and any(not(v>>i&1) for v in values) for i in range(n) if protected_mask>>i&1)
    protected_count=protected_mask.bit_count();baseline_safe=bool(worlds) and ambiguity(worlds)==protected_count
    packages=[];excluded=[]
    for row in sorted(bundle['packages'],key=lambda r:r['id']):
        queries=sorted((q['id'],cohort(q['members'])) for q in row['queries'])
        members=0
        for _,mask in queries:members|=mask
        authorized=row['approved'] and all(consent.get(people[i],{}).get('allowed',False) for i in range(n) if members>>i&1)
        if not authorized:excluded.append({'id':row['id'],'reason':'not_authorized'})
        elif row['utility']<policy['minimum_utility']:excluded.append({'id':row['id'],'reason':'below_utility_floor'})
        else:packages.append({'id':row['id'],'utility':row['utility'],'queries':queries})
    table=compile_policy(worlds,packages,protected_mask) if baseline_safe else None
    decision=None;publication=None;total=None;guaranteed=None;posterior=worlds
    if table is not None:
        decision=[{'world':world,'package':packages[k]['id']} for world,k in zip(worlds,table)]
        total=sum(packages[k]['utility'] for k in table);guaranteed=min(packages[k]['utility'] for k in table)
        chosen=packages[table[worlds.index(truth['current'])]]
        answer=tuple((truth['current']&mask).bit_count() for _,mask in chosen['queries'])
        publication={'package':chosen['id'],'counts':[{'id':name,'count':value} for (name,_),value in zip(chosen['queries'],answer)],'utility':chosen['utility']}
        posterior=[world for world,k in zip(worlds,table) if packages[k]['id']==chosen['id'] and tuple((world&mask).bit_count() for _,mask in chosen['queries'])==answer]
    ready=table is not None
    return {'ready':ready,'baseline_safe':baseline_safe,'baseline_candidate_count':len(worlds),'policy':decision,'total_utility':total,'guaranteed_utility':guaranteed,'publication':publication,'candidate_count':len(posterior),'protected_count':protected_count,'ambiguous_protected_count':ambiguity(posterior),'excluded_packages':excluded,'blocker_codes':[] if ready else ['prior_release_privacy_conflict'] if not baseline_safe else ['privacy_policy_floor_unreachable']}

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
