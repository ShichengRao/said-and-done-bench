"""Trusted oracle for h7-data-partner-export.

`transform` is the h6-data-redacted-export grader oracle (literal old/current pairs and
complete policy-table enumeration) and the case builders are that grader's cases.py,
both reused unchanged. Neither imports workspace code. Status/report fields are only
used here to decide whether a release must be written.
"""
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


# ---- h6 grader/cases.py (unchanged) ----
import copy,itertools,random


def public():
 return {'roster':{'people':['a','b'],'aliases':[],'consents':[{'person':p,'revision':1,'allowed':True} for p in ['a','b']]},'prior':[{'id':'published','epoch':'current','members':['a','b'],'count':1}],'packages':[{'id':'pool','queries':[{'id':'pool-count','members':['a','b']}],'utility':3,'approved':True}],'policy':{'max_changes':0,'protected':['a','b'],'minimum_utility':3},'snapshots':{'old':{'a':1,'b':0},'current':{'a':1,'b':0}}}


def small(seed):
 rng=random.Random(seed);people=['p'+str(i) for i in range(2+seed%2)]
 old={p:rng.randrange(2) for p in people};current={p:rng.randrange(2) for p in people}
 prior=[]
 for i in range(seed%3):
  epoch='old' if i%2==0 else 'current';members=rng.sample(people,rng.randrange(len(people)+1));prior.append(dict(id='prior'+str(i),epoch=epoch,members=members,count=sum((old if epoch=='old' else current)[p] for p in members)))
 packages=[]
 for i in range(3):
  queries=[dict(id='q'+str(i)+'-'+str(j),members=rng.sample(people,rng.randrange(len(people)+1))) for j in range(1+int((i+seed)%3==0))]
  packages.append(dict(id='package'+str(i),queries=queries,utility=1+rng.randrange(6),approved=(i+seed)%5!=0))
 return dict(roster=dict(people=people,aliases=[dict(alias='alias-'+p,target=p) for p in people],consents=[dict(person=p,revision=1,allowed=True) for p in people]),prior=prior,packages=packages,policy=dict(max_changes=sum(old[p]!=current[p] for p in people),protected=people if seed%2 else people[::2],minimum_utility=seed%5),snapshots=dict(old=old,current=current))


def private_worlds(source):
 people=sorted(source['roster']['people'])
 for old in [1,2,4,8]:
  for current in [3,5,6,9,10,12]:
   if (old^current).bit_count()!=1:continue
   b=copy.deepcopy(source);b['snapshots']={epoch:{p:(bits>>i)&1 for i,p in enumerate(people)} for epoch,bits in [('old',old),('current',current)]}
   yield b


def maximum_profile(source,degenerate=False):
 b=copy.deepcopy(source);b['policy']['max_changes']=2
 if degenerate:
  b['policy']['protected']=[];b['policy']['minimum_utility']=0
  for p in b['packages']:p['queries']=[];p['utility']=0
 return b


def cases(source):
 for seed in range(12):yield 'generated-'+str(seed),small(seed)
 yield 'public-policy-example',public()
 b=copy.deepcopy(source)
 for k in ['people','aliases','consents']:b['roster'][k].reverse()
 b['prior'].reverse();b['packages'].reverse();b['policy']['protected'].reverse()
 for row in b['prior']:row['members'].reverse()
 for package in b['packages']:
  package['queries'].reverse()
  for query in package['queries']:query['members'].reverse()
 yield 'unordered-records',b
 b=copy.deepcopy(source);b['roster']['aliases'].append(copy.deepcopy(b['roster']['aliases'][0]));yield 'identical-alias-replay',b
 b=copy.deepcopy(source);b['roster']['consents'].append(dict(person='p0',revision=2,allowed=False));yield 'whole-package-consent-withdrawal',b
 b=copy.deepcopy(source);b['roster']['consents']=[row for row in b['roster']['consents'] if row['person']!='p0'];yield 'absent-consent',b
 b=copy.deepcopy(source);next(p for p in b['packages'] if p['id']=='high')['approved']=False;yield 'unapproved-package',b
 b=copy.deepcopy(source);b['policy']['minimum_utility']=4;yield 'higher-floor-static-counterpart',b
 b=copy.deepcopy(source);b['policy']['minimum_utility']=5;yield 'unreachable-floor',b
 b=copy.deepcopy(source);b['policy']['minimum_utility']=0;b['packages']=[];yield 'no-configured-package',b
 b=copy.deepcopy(source);b['policy']['minimum_utility']=0;b['packages']=[dict(id='suppress',queries=[],utility=0,approved=True)];yield 'explicit-empty-package',b
 b=copy.deepcopy(source);b['packages'][0]['queries'].append(dict(id='empty-cohort',members=[]));yield 'empty-cohort-in-package',b
 b=copy.deepcopy(source);b['policy']['minimum_utility']=4;next(p for p in b['packages'] if p['id']=='medium')['queries'].append(dict(id='medium-control',members=['p3','p4']));yield 'two-count-output-tuple',b
 b=copy.deepcopy(source);b['policy']['protected']=[];yield 'empty-protected-set',b
 yield 'maximum-world-profile',maximum_profile(source)
 yield 'maximum-equal-utility-profile',maximum_profile(source,True)
 b=copy.deepcopy(source);b['prior']=[p for p in b['prior'] if p['epoch']=='current'];yield 'no-old-publications',b
 b=copy.deepcopy(source);b['prior'].append(dict(id='known-p0',epoch='current',members=['p0'],count=1));yield 'unsafe-fixed-baseline',b
 for i,b in enumerate(private_worlds(source)):yield 'private-world-'+str(i),b
 b=public();b['roster']['aliases']=[dict(alias='ghost-unused',target='absent')];yield 'invalid-unused-alias',b
 b=copy.deepcopy(source);b['roster']['aliases'].append(dict(alias='legacy-p1',target='p0'));yield 'invalid-conflicting-alias',b
 b=copy.deepcopy(source);b['roster']['aliases'] += [dict(alias='cycle-a',target='cycle-b'),dict(alias='cycle-b',target='cycle-a')];yield 'invalid-unused-cycle',b
 b=copy.deepcopy(source);b['packages'][0]['queries'][0]['members'].append('absent');yield 'invalid-unknown-member',b
 b=copy.deepcopy(source);b['policy']['max_changes']=0;yield 'invalid-private-transition',b
 b=copy.deepcopy(source);b['prior'][0]['count']=2;yield 'invalid-private-count',b


def independent_checks(transform,source):
 r=transform(copy.deepcopy(source))
 assert r['ready'] and r['baseline_safe'] and r['baseline_candidate_count']==6
 assert r['policy']==[dict(world=w,package=p) for w,p in zip([3,5,6,9,10,12],['cross','high','high','high','high','cross'])]
 assert r['total_utility']==26 and r['guaranteed_utility']==3 and r['candidate_count']==2
 assert r['protected_count']==r['ambiguous_protected_count']==3
 assert r['publication']==dict(package='cross',counts=[dict(id='cross-count',count=1)],utility=3)
 for b in private_worlds(source):assert transform(b)['policy']==r['policy']
 b=copy.deepcopy(source);b['policy']['minimum_utility']=4;out=transform(b)
 assert out['ready'] and out['total_utility']==24 and out['guaranteed_utility']==4
 b['policy']['minimum_utility']=5;out=transform(b)
 assert not out['ready'] and out['policy'] is None and out['publication'] is None


def cli_success_cases():return [('public-policy',public()),('generated',small(7))]


# ---- h7 adapter ----
import json
from pathlib import Path

FILES = ('roster', 'prior', 'packages', 'policy', 'snapshots')
KEYS = ('policy', 'total_utility', 'guaranteed_utility', 'publication', 'baseline_candidate_count',
        'candidate_count', 'protected_count', 'ambiguous_protected_count', 'excluded_packages')


def read_data(root):
    return {name: json.loads((Path(root) / ('%s.json' % name)).read_text()) for name in FILES}


def write_data(root, bundle):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        (root / ('%s.json' % name)).write_text(json.dumps(bundle[name], indent=2) + '\n')


def expected(bundle):
    """The release document the command must write, or None when it must refuse."""
    try:
        result = transform(copy.deepcopy(bundle))
    except ValueError:
        return None
    return {key: result[key] for key in KEYS} if result['ready'] else None


def compare(document, bundle):
    want = expected(bundle)
    if want is None:
        return ['no release should be written for these records']
    if not isinstance(document, dict):
        return ['release is not an object']
    return ['%s differs' % key for key in KEYS if document.get(key) != want[key]]


def nearby_cases(source):
    yield from cases(source)
