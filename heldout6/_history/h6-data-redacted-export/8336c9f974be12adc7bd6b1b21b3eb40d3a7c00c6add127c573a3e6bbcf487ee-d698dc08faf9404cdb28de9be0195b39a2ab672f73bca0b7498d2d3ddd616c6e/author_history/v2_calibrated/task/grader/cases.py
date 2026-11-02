import copy,random

def small(seed):
 rng=random.Random(seed);n=2+seed%4;people=['p'+str(i) for i in range(n)];old={p:rng.randrange(2) for p in people};current={p:rng.randrange(2) for p in people};limit=sum(old[p]!=current[p] for p in people)
 aliases=[dict(alias='alias-'+p,target=p) for p in people]
 prior=[]
 for i in range(seed%4):
  epoch='old' if i%2==0 else 'current';members=rng.sample(people,rng.randrange(n+1));prior.append(dict(id='prior'+str(i),epoch=epoch,members=members,count=sum((old if epoch=='old' else current)[p] for p in members)))
 queries=[dict(id='q'+str(i),members=rng.sample(people,rng.randrange(n+1)),utility=1+rng.randrange(8),approved=(i+seed)%5!=0) for i in range(4)]
 return dict(roster=dict(people=people,aliases=aliases,consents=[dict(person=p,revision=1,allowed=True) for p in people]),prior=prior,queries=queries,policy=dict(max_changes=limit,protected=people if seed%2 else people[::2],minimum_utility=5),snapshots=dict(old=old,current=current))

def public():
 return {'roster':{'people':['a','b'],'aliases':[],'consents':[{'person':'a','revision':1,'allowed':True},{'person':'b','revision':1,'allowed':True}]},'prior':[],'queries':[{'id':'total','members':['a','b'],'utility':3,'approved':True}],'policy':{'max_changes':2,'protected':['a','b'],'minimum_utility':3},'snapshots':{'old':{'a':0,'b':1},'current':{'a':0,'b':1}}}

def cases(source):
 for seed in range(12):yield 'generated-'+str(seed),small(seed)
 yield 'public-count-example',public()
 b=copy.deepcopy(source)
 for k in ['people','aliases','consents']:b['roster'][k].reverse()
 b['prior'].reverse();b['queries'].reverse();b['policy']['protected'].reverse()
 for row in b['prior']+b['queries']:row['members'].reverse()
 yield 'unordered-records',b
 b=copy.deepcopy(source);b['roster']['aliases'].append(copy.deepcopy(b['roster']['aliases'][0]));yield 'identical-alias-replay',b
 b=copy.deepcopy(source);b['roster']['consents'].append(dict(person='p0',revision=3,allowed=False));yield 'whole-query-current-withdrawal',b
 b=copy.deepcopy(source);b['queries']=[q for q in b['queries'] if q['id']!='unapproved'];b['roster']['consents']=[c for c in b['roster']['consents'] if c['person']!='p0'];yield 'absent-consent-is-not-bit-evidence',b
 b=copy.deepcopy(source);b['queries']=[q for q in b['queries'] if q['id']!='unapproved'];b['queries'].append(dict(id='empty',members=[],utility=2,approved=True));yield 'empty-current-query',b
 b=copy.deepcopy(source);b['policy']['minimum_utility']=42;yield 'unreachable-utility-floor',b
 b=copy.deepcopy(source);b['policy']['minimum_utility']=0;b['queries']=[];yield 'no-new-queries',b
 b=copy.deepcopy(source);b['policy']['protected']=[];yield 'empty-protected-set',b
 b=copy.deepcopy(source);b['policy']['max_changes']=8;yield 'actually-looser-transition-bound',b
 b=copy.deepcopy(source);b['prior']=[q for q in b['prior'] if q['epoch']=='current'];yield 'no-old-publications',b
 b=copy.deepcopy(source);b['prior']=[dict(id='known-p0',epoch='current',members=['p0'],count=b['snapshots']['current']['p0'])];yield 'baseline-already-determines-protected-bit',b
 b=copy.deepcopy(source);b['prior']=[dict(id='known-p0',epoch='old',members=['p0'],count=b['snapshots']['old']['p0'])];b['policy']['max_changes']=8;yield 'old-bit-not-current-bit',b
 b=copy.deepcopy(source);b['snapshots']['old']={p:int((60>>i)&1) for i,p in enumerate(sorted(b['roster']['people']))};b['snapshots']['current']={p:int((57>>i)&1) for i,p in enumerate(sorted(b['roster']['people']))};yield 'different-private-world-same-public-evidence',b
 b=public();b['policy']['max_changes']=0;yield 'identical-epoch-restriction',b
 b=public();b['roster']['aliases']=[dict(alias='ghost-unused',target='absent')];yield 'invalid-unused-alias',b
 b=copy.deepcopy(source);b['roster']['aliases'].append(dict(alias='legacy-p1',target='p0'));yield 'invalid-conflicting-alias',b
 b=copy.deepcopy(source);b['roster']['aliases'] += [dict(alias='cycle-a',target='cycle-b'),dict(alias='cycle-b',target='cycle-a')];yield 'invalid-unused-cycle',b
 b=copy.deepcopy(source);b['queries'][0]['members'].append('absent');yield 'invalid-unknown-member',b
 b=copy.deepcopy(source);b['policy']['max_changes']=1;yield 'invalid-private-transition-contradiction',b
 b=copy.deepcopy(source);b['prior'][0]['count']+=1;yield 'invalid-private-count-contradiction',b

def independent_checks(transform,source):
 r=transform(copy.deepcopy(source));assert r['ready'] and r['baseline_safe'] and r['utility']==41
 assert r['selected']==['q0','q1','q3','q7'] and r['baseline_candidate_count']==70 and r['candidate_count']==4
 assert r['protected_count']==r['ambiguous_protected_count']==8
 assert r['publication']==[dict(id='q0',count=2,utility=9),dict(id='q1',count=2,utility=10),dict(id='q3',count=2,utility=10),dict(id='q7',count=2,utility=12)]
 b=copy.deepcopy(source);b['roster']['consents'].append(dict(person='p0',revision=3,allowed=False));r=transform(b)
 assert not r['ready'] and r['utility']==32 and r['selected']==['q1','q3','q7']
 assert transform(public())['publication']==[dict(id='total',count=1,utility=3)]

def cli_success_cases():return [('public-count',public()),('generated',small(7))]
