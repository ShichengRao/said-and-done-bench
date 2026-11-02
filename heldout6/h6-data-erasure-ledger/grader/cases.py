import copy,random

def override(b,node,allow):
 b['policies'].append(dict(node=node,revision=50,known=b['catalog']['at'],effective_at=b['catalog']['at'],approved=True,allow=allow,cost=next(p['cost'] for p in b['policies'] if p['node']==node and p['revision']==1)))

def tiny():
 row=dict(key='x',deleted=False,tenant='t',alias='a',at=1,payload={'x':1})
 return dict(catalog=dict(watermark=0,cutover=0,at=2,nodes=[dict(id='N',object='o',parents=[],rows=[row])],heads={'o':'N'}),changes=[],identity=[dict(tenant='t',alias='a',subject='s',**{'from':0,'until':None})],requests=[dict(id='r',tenant='t',subject='s',through=1)],holds=[],policies=[dict(node='N',revision=1,known=0,effective_at=0,approved=True,allow=True,cost=2)],reviewable_nodes=['N'])

def cases(source):
 b=copy.deepcopy(source)
 for k in ['changes','identity','requests','holds','policies']:b[k].reverse()
 b['catalog']['nodes'].reverse();b['catalog']['nodes']+=copy.deepcopy(b['catalog']['nodes'][:1]);b['identity']+=copy.deepcopy(b['identity'][:1]);yield 'order-and-duplicates',b
 b=copy.deepcopy(source);override(b,'S',False);yield 'root-rewrites-required',b
 b=copy.deepcopy(source);override(b,'S',False);override(b,'R1',False);yield 'owner-approval-required',b
 b=copy.deepcopy(source);override(b,'S',False);override(b,'R1',False);b['reviewable_nodes']=[];yield 'no-listed-owner-remedy',b
 b=copy.deepcopy(source);b['changes']=[e for e in b['changes'] if e['seq']!=12];yield 'current-head-changes-sharing-optimum',b
 b=copy.deepcopy(source);b['holds']=[];yield 'hold-release-changes-physical-purge',b
 b=copy.deepcopy(source);b['requests']=[];yield 'no-erasure-zero-rewrites',b
 b=copy.deepcopy(source);next(n for n in b['catalog']['nodes'] if n['id']=='S')['rows'].append(dict(key='x',deleted=True));yield 'existing-tombstone-barrier',b
 b=copy.deepcopy(source);b['changes'].append(dict(seq=10,object='different',op='delete'));yield 'covered-conflict',b
 b=copy.deepcopy(source);b['changes'].append(dict(seq=99,object='ignored',op='head',node='absent'));yield 'future-garbage-ignored',b
 b=copy.deepcopy(source);b['catalog']['nodes'][0]['parents']=['absent'];yield 'missing-ancestor',b
 b=copy.deepcopy(source);next(n for n in b['catalog']['nodes'] if n['id']=='B')['parents']=['S'];yield 'lineage-cycle',b
 b=copy.deepcopy(source);b['identity'].append(dict(tenant='t',alias='reused',subject='conflict',**{'from':1,'until':3}));yield 'ambiguous-history',b
 b=copy.deepcopy(source);b['holds'].append(dict(id='missing-hold',node='absent',**{'from':0,'until':None}));yield 'missing-active-hold',b
 b=copy.deepcopy(source);b['holds'].append(dict(id='inactive',node='absent',**{'from':100,'until':None}));yield 'inactive-missing-hold',b
 b=copy.deepcopy(source);q=copy.deepcopy(next(p for p in b['policies'] if p['node']=='S' and p['revision']==3));q['cost']+=1;b['policies'].append(q);yield 'draft-policy-conflict',b
 b=copy.deepcopy(source);b['catalog']['heads']['invalid']='absent';yield 'invalid-snapshot-head',b
 b=copy.deepcopy(source);q=copy.deepcopy(b['catalog']['nodes'][0]);q['rows']=[];b['catalog']['nodes'].append(q);yield 'conflicting-immutable-node',b
 rng=random.Random(67235)
 for case in range(14):
  b=tiny();b['catalog']['nodes']=[];b['catalog']['heads']={};b['policies']=[];b['reviewable_nodes']=[]
  for i in range(5):
   n='N'+str(i);parents=rng.sample(['N'+str(j) for j in range(i)],min(i,rng.randrange(3)))
   rows=[dict(key='k'+str(rng.randrange(3)),deleted=False,tenant='t',alias='a',at=rng.choice([1,3]),payload={'node':n})]
   if rng.randrange(4)==0:rows=[dict(key='k'+str(rng.randrange(3)),deleted=True)]
   b['catalog']['nodes'].append(dict(id=n,object='o'+str(i),parents=parents,rows=rows));b['policies'].append(dict(node=n,revision=1,known=0,effective_at=0,approved=True,allow=bool(rng.randrange(2)),cost=rng.randrange(5)))
   if i<4:b['reviewable_nodes'].append(n)
  b['catalog']['heads']={'o3':'N3','o4':'N4'}
  if case%2:b['holds']=[dict(id='h',node='N2',**{'from':0,'until':None})]
  yield 'bounded-random-DAG-'+str(case),b

def independent_checks(transform,source):
 r=transform(copy.deepcopy(source));assert r['ready'] and r['plan']['cost']==4
 assert [x['original'] for x in r['plan']['rewrites']]==['S']
 assert r['plan']['purge_nodes']==['O','S','U','X'] and r['plan']['live_originals']==['C','N','R1','R2']
 assert r['retained_for_hold']==[{'node':'B','holds':['legal-H']},{'node':'H','holds':['legal-H']}]
 clone=r['plan']['rewrites'][0];assert {'key':'x','deleted':True} in clone['rows']
 # Literal independent overlay shows why omission of the clean-clone barrier is unsafe.
 clean=next(n for n in source['catalog']['nodes'] if n['id']=='C')
 merged={row['key']:row for row in clean['rows']};merged.update({row['key']:row for row in clone['rows'] if row['key']!='x'})
 assert merged['x']['payload']=={'value':'must-not-resurrect'}
 orders=next(v for v in r['plan']['logical_views'] if v['object']=='orders');assert 'x' not in {x['key'] for x in orders['rows']}
 b=copy.deepcopy(source);override(b,'S',False);q=transform(b);assert q['plan']['cost']==6 and [x['original'] for x in q['plan']['rewrites']]==['R1','R2']
 override(b,'R1',False);q=transform(b);assert not q['ready'] and q['plan'] is None and q['owner_review']['approval_nodes']==['B'] and q['owner_review']['plan']['cost']==1
 b=copy.deepcopy(source);b['changes']=[e for e in b['changes'] if e['seq']!=12];q=transform(b);assert q['plan']['cost']==3 and [x['original'] for x in q['plan']['rewrites']]==['R1']
 b=tiny();q=transform(b);assert q['plan']['rewrites'][0]['rows']==[{'key':'x','deleted':True}]
 b['requests']=[];q=transform(b);assert q['plan']['cost']==0 and q['plan']['rewrites']==[]

def cli_success_cases():return [('tiny-erasure',tiny())]
