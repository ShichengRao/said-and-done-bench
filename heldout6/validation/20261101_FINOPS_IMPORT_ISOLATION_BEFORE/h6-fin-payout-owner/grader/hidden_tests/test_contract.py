import copy,json,random,subprocess,sys
from pathlib import Path
import pytest
from settlement import analyze
from independent import oracle,resolve,scan

def request():return json.loads(Path('data/request.json').read_text())

def test_production_tuple_state_certificate():
 b=request();r=analyze(b);assert r==oracle(b)
 assert r['reachable_states']==129 and r['settled_cents']==36 and not r['complete']
 assert r['owner_review']['proposals']==['early-D-bridge']

def test_distinct_timing_relaxations_and_positive_final_cash():
 b=request();a=resolve(b)
 balances={w['id']:w['balance'] for w in b['wallets']}
 for p in a['payouts']:balances[a['owners'][p['source_owner']]]-=p['cents'];balances[a['owners'][p['destination_owner']]]+=p['cents']
 assert all(v>0 for v in balances.values())
 alt=copy.deepcopy(a);alt['payouts'][0]['receipt_after']=[];r=scan(b['wallets'],alt);assert r['complete'] and r['reachable_states']==261
 alt=copy.deepcopy(a);alt['leases'][3]['activate_after']=[];r=scan(b['wallets'],alt);assert r['complete'] and r['reachable_states']==168
 for p in b['proposals']:
  alt=copy.deepcopy(b)
  for kind in ['owners','payouts','leases']:
   for row in p[kind]:alt[kind].append(dict(**row,revision=50,known=20,signed=True,void=False))
  assert analyze(alt)==oracle(alt) and analyze(alt)['complete']

def test_reordering_duplicates_and_immutability():
 b=request();before=copy.deepcopy(b);expected=analyze(b)
 assert b==before
 for key in ['wallets','owners','payouts','leases','proposals']:b[key].reverse()
 for key in ['owners','payouts','leases']:b[key]+=copy.deepcopy(b[key][:2])
 assert analyze(b)==expected

def test_visible_conflicts_and_future_ignored():
 b=request();r=copy.deepcopy(next(r for r in b['payouts'] if r['revision']==3));r['cents']+=1;b['payouts'].append(r)
 with pytest.raises(ValueError):analyze(b)
 b=request();r=copy.deepcopy(next(r for r in b['payouts'] if r['revision']==4));r['cents']+=1;b['payouts'].append(r)
 assert analyze(b)==analyze(request())

def test_repay_requires_receipt_and_cash_even_after_all_payouts():
 def s(**row):return dict(**row,revision=1,known=1,signed=True,void=False)
 b=dict(as_of=1,wallets=[dict(id='A',balance=0),dict(id='B',balance=0)],owners=[s(id='a',wallet='A'),s(id='b',wallet='B')],payouts=[s(id='p',source_owner='a',destination_owner='b',cents=2,receipt_after=[])],leases=[s(id='L',owner='a',cents=2,activate_after=[],release_after=['p'])],proposals=[])
 r=analyze(b);assert r==oracle(b) and r['settled_cents']==2 and not r['complete'] and r['active_lease']=='L'

def test_generated_finite_graph_oracle():
 rng=random.Random(6925)
 for case in range(20):
  def s(**row):return dict(**row,revision=1,known=1,signed=True,void=False)
  b=dict(as_of=1,wallets=[dict(id=x,balance=rng.randrange(5)) for x in 'ABC'],owners=[s(id='o'+x,wallet=x) for x in 'ABC'],payouts=[],leases=[],proposals=[])
  for i in range(3):
   a,z=rng.sample(list('ABC'),2);b['payouts'].append(s(id='P'+str(i),source_owner='o'+a,destination_owner='o'+z,cents=rng.randrange(1,5),receipt_after=['P'+str((i+1)%3)] if rng.randrange(3)==0 else []))
  for i in range(2):b['leases'].append(s(id='L'+str(i),owner='o'+rng.choice('ABC'),cents=rng.randrange(1,4),activate_after=['P0'] if rng.randrange(2) else [],release_after=['P1'] if rng.randrange(2) else []))
  assert analyze(b)==oracle(b),case

def test_cli_json_contract():
 p=subprocess.run([sys.executable,'settlement.py','data/request.json'],capture_output=True,text=True,timeout=30)
 assert p.returncode==0 and json.loads(p.stdout)==analyze(request())
