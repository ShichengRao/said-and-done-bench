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
