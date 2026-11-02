import copy,itertools,json,subprocess,sys,time
from pathlib import Path
import pytest
import procurement as p

def catalog():
 return dict(warehouses={'east':dict(unit_fee=0,activation_fee=1),'west':dict(unit_fee=0,activation_fee=1)},recipes={'alpha':{'a':dict(ingredients={'red':2},cost=0),'b':dict(ingredients={'blue':1},cost=4)},'beta':{'a':dict(ingredients={'red':1},cost=4),'b':dict(ingredients={'blue':2},cost=0)},'red':{'only':dict(ingredients={'red':1},cost=0)},'blue':{'only':dict(ingredients={'blue':1},cost=0)}},stock=[dict(warehouse=w,ingredient=i,quantity=q) for w,i,q in [('east','red',1),('east','blue',2),('west','red',2),('west','blue',1)]])
def request(product,warehouses):return dict(needs={product:1},warehouses=warehouses)
def reserve(db,op,basket,product,warehouses,at=1,until=100):return p.apply(db,dict(operation_id=op,at=at,kind='reserve',basket=basket,until=until,request=request(product,warehouses)))
def setup(tmp_path):
 db=str(tmp_path/'db');p.initialize(db,catalog());reserve(db,'hold-red','third-red','red',['east']);reserve(db,'hold-blue','third-blue','blue',['west']);reserve(db,'old-a','a','alpha',['west']);reserve(db,'old-b','b','beta',['east']);return db

def exchange(entries,op='joint',at=2):return dict(operation_id=op,at=at,kind='exchange',entries=entries)
def replacements():return [dict(basket='a',expected_version=1,until=200,request=request('beta',['east'])),dict(basket='b',expected_version=1,until=200,request=request('alpha',['west']))]
def exhaustive(cat,reqs,available):
 slots=[]
 for bid,r in sorted(reqs.items()):
  for product,n in sorted(r['needs'].items()):
   for ordinal in range(n):slots.append((bid,product,ordinal,[(recipe,w) for recipe in sorted(cat['recipes'][product]) for w in sorted(r['warehouses'])]))
 answers=[]
 for choices in itertools.product(*(s[3] for s in slots)):
  used={};opens=set();cost=0;vector=[]
  for (bid,product,ordinal,_),(recipe,w) in zip(slots,choices):
   desc=cat['recipes'][product][recipe];cost+=desc['cost']+cat['warehouses'][w]['unit_fee'];opens.add((bid,w));vector.append((bid,product,ordinal,recipe,w))
   for ing,q in desc['ingredients'].items():used[(w,ing)]=used.get((w,ing),0)+q
  cost+=sum(cat['warehouses'][w]['activation_fee'] for bid,w in opens)
  if all(q<=available.get(k,0) for k,q in used.items()):answers.append((cost,tuple(vector)))
 return min(answers) if answers else None

def test_joint_exchange_succeeds_while_each_alone_is_unavailable(tmp_path):
 db=setup(tmp_path);before=p.snapshot(db)
 for i,e in enumerate(replacements()):
  out=p.apply(db,exchange([e],op='alone'+str(i)));assert out['result']=='unavailable' and out['baskets'][0]['version']==1
 out=p.apply(db,exchange(replacements()));assert out['result']=='exchanged' and [b['version'] for b in out['baskets']]==[2,2]
 assert out['baskets'][0]['units'][0]['warehouse']=='east' and out['baskets'][1]['units'][0]['warehouse']=='west'
 assert all(r['available']==0 for r in p.snapshot(db)['stock'])
 assert [b for b in p.snapshot(db)['baskets'] if b['id'].startswith('third')]==[b for b in before['baskets'] if b['id'].startswith('third')]

def test_joint_plan_matches_independent_exhaustive_objective(tmp_path):
 cat=catalog();cat['stock']=[{**r,'quantity':4} for r in cat['stock']];db=str(tmp_path/'db');p.initialize(db,cat)
 for i,needs in enumerate([{'alpha':1,'beta':1},{'alpha':2},{'beta':2}]):
  req=dict(needs=needs,warehouses=['west','east']);out=p.apply(db,dict(operation_id='r'+str(i),at=i+1,kind='reserve',basket=str(i),until=50,request=req));snap=p.snapshot(db)
  prior_held={}
  for b in snap['baskets']:
   if b['id']!=str(i) and b['status']=='held':
    for row in b['ingredients']:key=(row['warehouse'],row['ingredient']);prior_held[key]=prior_held.get(key,0)+row['quantity']
  avail={(r['warehouse'],r['ingredient']):r['quantity']-prior_held.get((r['warehouse'],r['ingredient']),0) for r in cat['stock']};best=exhaustive(cat,{str(i):req},avail)
  if best is None:assert out['result']=='unavailable'
  else:
   b=out['baskets'][0];vec=tuple((str(i),u['product'],u['ordinal'],u['recipe'],u['warehouse']) for u in b['units']);assert (b['cost'],vec)==best

def test_greedy_recipe_can_starve_later_product(tmp_path):
 cat=catalog();cat['warehouses']={'west':dict(unit_fee=0,activation_fee=0)};cat['stock']=[dict(warehouse='west',ingredient='red',quantity=2),dict(warehouse='west',ingredient='blue',quantity=1)];db=str(tmp_path/'db');p.initialize(db,cat)
 req=dict(needs={'alpha':1,'red':1},warehouses=['west']);out=p.apply(db,dict(operation_id='r',at=1,kind='reserve',basket='x',until=10,request=req));assert out['result']=='reserved';assert out['baskets'][0]['units'][0]['recipe']=='b'

def test_failed_exchange_retains_old_hold_and_history(tmp_path):
 db=setup(tmp_path);old=p.snapshot(db);e=replacements()[0];out=p.apply(db,exchange([e]));assert out['result']=='unavailable';now=p.snapshot(db);assert now['baskets']==old['baskets'] and now['history'][:-1]==old['history'];assert now['clock']==2

def test_expiration_rolls_back_on_error_and_commits_on_unavailable(tmp_path):
 db=str(tmp_path/'db');p.initialize(db,catalog());reserve(db,'r','a','alpha',['west'],until=3);old=p.snapshot(db)
 with pytest.raises(ValueError):p.apply(db,dict(operation_id='bad',at=3,kind='commit',basket='a',expected_version=1))
 assert p.snapshot(db)==old
 req=dict(needs={'alpha':6},warehouses=['west']);out=p.apply(db,dict(operation_id='bad',at=3,kind='reserve',basket='x',until=9,request=req));assert out['result']=='unavailable';assert p.snapshot(db)['baskets'][0]['status']=='expired'

def test_replay_before_clock_payload_conflict_and_no_aliases(tmp_path):
 db=setup(tmp_path);command=exchange(replacements());out=p.apply(db,command);frozen=copy.deepcopy(out);p.apply(db,dict(operation_id='later',at=4,kind='tick'));out['baskets'][0]['units'].clear();assert p.apply(db,command)==frozen
 with pytest.raises(ValueError):p.apply(db,{**command,'at':4})

def test_commit_release_terminal_ids_and_physical_conservation(tmp_path):
 db=setup(tmp_path);p.apply(db,dict(operation_id='commit',at=2,kind='commit',basket='a',expected_version=1));p.apply(db,dict(operation_id='release',at=2,kind='release',basket='b',expected_version=1));rows={(r['warehouse'],r['ingredient']):r for r in p.snapshot(db)['stock']};assert rows['west','red']['on_hand']==0 and rows['east','blue']['available']==2
 with pytest.raises(ValueError):reserve(db,'reuse','a','alpha',['west'],at=2)

def test_catalog_order_unknown_route_and_input_preservation(tmp_path):
 db=str(tmp_path/'db');cat=catalog();old=copy.deepcopy(cat);p.initialize(db,cat);assert cat==old;cat['stock'].reverse();assert p.initialize(db,cat)==p.snapshot(db)
 with pytest.raises(ValueError):reserve(db,'bad','b','red',['east','unknown'])
 assert p.snapshot(db)['history']==[]

def test_fresh_interpreter_replay_and_inspection(tmp_path):
 db=setup(tmp_path);command=exchange(replacements());out=p.apply(db,command)
 script="import json,sys,procurement; p=sys.argv[1]; q=json.loads(sys.argv[2]); print(json.dumps({'replay':procurement.apply(p,q),'snapshot':procurement.snapshot(p)}))"
 run=subprocess.run([sys.executable,'-c',script,db,json.dumps(command)],capture_output=True,text=True,timeout=15);assert run.returncode==0,run.stderr;actual=json.loads(run.stdout);assert actual['replay']==out and actual['snapshot']==p.snapshot(db)

def test_two_process_competing_reservations(tmp_path):
 cat=catalog();cat['stock']=[{**r,'quantity':1 if r['warehouse']=='east' and r['ingredient']=='red' else 0} for r in cat['stock']];db=str(tmp_path/'db');p.initialize(db,cat);gate=tmp_path/'go'
 script="""import json,pathlib,sys,time,procurement
p,ready,gate,bid=sys.argv[1:];pathlib.Path(ready).touch()
while not pathlib.Path(gate).exists():time.sleep(.005)
q={'operation_id':bid,'at':1,'kind':'reserve','basket':bid,'until':10,'request':{'needs':{'red':1},'warehouses':['east']}}
print(json.dumps(procurement.apply(p,q)))
"""
 children=[subprocess.Popen([sys.executable,'-c',script,db,str(tmp_path/('ready'+str(i))),str(gate),str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for i in range(2)];deadline=time.monotonic()+10
 while not all((tmp_path/('ready'+str(i))).exists() for i in range(2)) and time.monotonic()<deadline:time.sleep(.005)
 gate.touch();out=[x.communicate(timeout=15) for x in children];assert all(x.returncode==0 for x in children),out;assert sorted(json.loads(o)['result'] for o,e in out)==['reserved','unavailable'];assert all(r['available']>=0 for r in p.snapshot(db)['stock'])

def test_activation_cost_requires_joint_unit_choice(tmp_path):
 cat=catalog();cat['warehouses']={'east':dict(unit_fee=0,activation_fee=3),'west':dict(unit_fee=1,activation_fee=0)};cat['stock']=[{**x,'quantity':4} for x in cat['stock']];db=str(tmp_path/'db');p.initialize(db,cat)
 out=p.apply(db,dict(operation_id='plan',at=1,kind='reserve',basket='b',until=10,request={'needs':{'red':4},'warehouses':['west','east']}))
 assert out['baskets'][0]['cost']==3 and all(u['warehouse']=='east' for u in out['baskets'][0]['units'])

def test_generated_cost_capacity_and_order_against_exhaustive_oracle(tmp_path):
 import random
 rng=random.Random(4302)
 for i in range(12):
  cat=catalog()
  for w in cat['warehouses'].values():w['activation_fee']=rng.randrange(5);w['unit_fee']=rng.randrange(3)
  for row in cat['stock']:row['quantity']=rng.randrange(5)
  req={'needs':{'alpha':rng.randrange(1,3),'beta':rng.randrange(1,3)},'warehouses':['west','east']}
  expected=exhaustive(cat,{'b':req},{(r['warehouse'],r['ingredient']):r['quantity'] for r in cat['stock']})
  db=str(tmp_path/('db'+str(i)));p.initialize(db,cat);out=p.apply(db,dict(operation_id='plan',at=1,kind='reserve',basket='b',until=10,request=req))
  if expected is None:assert out['result']=='unavailable'
  else:
   b=out['baskets'][0];vector=tuple(('b',u['product'],u['ordinal'],u['recipe'],u['warehouse']) for u in b['units']);assert (b['cost'],vector)==expected
