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

