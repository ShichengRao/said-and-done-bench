import copy,json,random,subprocess,sys
from pathlib import Path
import pytest
from recognition import analyze
from independent import oracle,resolve,solve

def request():return json.loads(Path('data/request.json').read_text())

def test_production_recursive_decimal_certificate():
 b=request();r=analyze(b);assert r==oracle(b)
 assert r['legal_assignments']==58 and [x+56 for x in r['attainable_period_cents']]==[208,211,213,215,218,219,222,224,226,229,232,234,236,239,243]
 assert not r['complete'] and r['chosen']['period_cents']==162 and r['owner_review']['proposals']==['B-price']

def test_interior_gap_requires_current_terms_and_frozen_provenance():
 b=request();a=resolve(b);r=solve(a,161);assert min(r['attainable_period_cents'])<161<max(r['attainable_period_cents'])
 old=copy.deepcopy(a)
 for t in old['terms']:
  if t['id']=='A':t['price_cents']=90
  if t['id']=='B':t['price_cents']=122
 assert solve(old,161)['complete'] and solve(a,161,freeze=False)['complete']
 assert not solve(a,161)['complete']
 aonly=copy.deepcopy(a);aonly['terms'][0]['price_cents']=90;assert not solve(aonly,161)['complete']

@pytest.mark.parametrize('which',['B-price','correct-ticket'])
def test_authorized_counterfactual_under_identical_rules(which):
 b=request();p=next(p for p in b['proposals'] if p['id']==which)
 for t in p['terms']:b['terms'].append(dict(**t,effective_period=2,revision=50,known=20,signed=True,void=False))
 if p['requested_period_cents'] is not None:b['requested_period_cents']=p['requested_period_cents']
 r=analyze(b);assert r==oracle(b) and r['complete'] and r['opening_cents']==56
 assert r['owner_review']['proposals']==[]

def test_reorder_duplicate_delivery_and_no_input_mutation():
 b=request();before=copy.deepcopy(b);expected=analyze(b);assert b==before
 for k in ['terms','receipts','postings','proposals']:b[k].reverse()
 for k in ['terms','receipts','postings']:b[k]+=copy.deepcopy(b[k][:2])
 assert analyze(b)==expected

def test_conflicts_in_ineligible_visible_revision_still_rejected():
 b=request();r=copy.deepcopy(next(r for r in b['terms'] if r['revision']==4));r['price_cents']+=1;b['terms'].append(r)
 with pytest.raises(ValueError):analyze(b)
 b=request();r=copy.deepcopy(b['receipts'][0]);r.update(revision=20,known=100,units=20);b['receipts'].append(r);assert analyze(b)==analyze(request())

def test_no_attribution_is_distinct_from_interior_gap():
 b=request()
 for r in b['terms']:r['required_units']=1
 r=analyze(b);assert r==oracle(b) and r['legal_assignments']==0 and r['chosen'] is None and r['attainable_period_cents']==[]

def test_generated_partial_rounding_frozen_and_negative_catchup():
 rng=random.Random(6937)
 for case in range(25):
  def row(**p):return dict(**p,revision=1,known=1,signed=True,void=False)
  b=dict(as_of=2,period=2,requested_period_cents=rng.randrange(-15,30),terms=[row(id=n,effective_period=1,price_cents=rng.randrange(1,25),required_units=rng.randrange(3,9)) for n in 'ABC'],receipts=[row(id='H',period=1,units=1,eligible=['A','B'])],postings=[row(id='post',period=1,receipt='H',obligation='A',units=1,booked_cents=rng.randrange(20))],proposals=[])
  for i in range(4):b['receipts'].append(row(id='R'+str(i),period=2,units=rng.randrange(1,4),eligible=sorted(rng.sample(list('ABC'),rng.randrange(1,4)))))
  b['proposals']=[dict(id='B-new-price',cost=1,terms=[dict(id='B',price_cents=7,required_units=9)],requested_period_cents=None)]
  assert analyze(b)==oracle(b),case

def test_cli_json_contract():
 p=subprocess.run([sys.executable,'recognition.py','data/request.json'],capture_output=True,text=True,timeout=30)
 assert p.returncode==0 and json.loads(p.stdout)==analyze(request())
