import copy,itertools,json,random,subprocess,sys
from pathlib import Path
import pytest
from funding import analyze
from independent import oracle,authority,solve

def request():return json.loads(Path('data/request.json').read_text())

def test_production_independent_cartesian_audit():
 b=request();assert analyze(b)==oracle(b)
 r=analyze(b);assert r['funded_cents']==530 and r['owner_review']['cost']==2
 assert r['owner_review']['proposals']==['cash-A','cash-C']

def test_production_obstacle_needs_three_phases_and_both_resources():
 b=request();rs=authority(b);fc={x['id']:x['cap'] for x in b['facilities']};pc={x['id']:x['cap'] for x in b['collateral']}
 for phases in itertools.combinations(range(3),2):assert solve(b,rs,fc,pc,phases)['funded_cents']==600
 assert solve(b,rs,{k:10000 for k in fc},pc)['funded_cents']==600
 assert solve(b,rs,fc,{k:10000 for k in pc})['funded_cents']==600
 assert solve(b,rs,fc,pc)['funded_cents']==530

def test_signed_history_and_owner_counterfactual():
 b=request();b['routes']=[r for r in b['routes'] if not(r['id']=='R0-1' and r['revision']==2)]
 assert analyze(b)==oracle(b) and analyze(b)['complete']
 b=request();b['facilities'][0]['cap']+=100;b['facilities'][2]['cap']+=20
 assert analyze(b)==oracle(b) and analyze(b)['complete']

def test_reorder_exact_duplicates_and_input_immutability():
 b=request();expected=analyze(b);before=copy.deepcopy(b)
 for key in ['obligations','routes','facilities','collateral','proposals']:b[key].reverse()
 b['routes']+=copy.deepcopy(b['routes'][:3]);assert analyze(b)==expected
 assert analyze(before)==expected and before==request()

def test_visible_conflicts_even_unsigned_superseded_and_future_ignored():
 b=request();r=next(r for r in b['routes'] if r['id']=='R0-1' and r['revision']==3);q=copy.deepcopy(r);q['pledge_cents']+=1;b['routes'].append(q)
 with pytest.raises(ValueError):analyze(b)
 b=request();r=next(r for r in b['routes'] if r['id']=='R0-1' and r['revision']==4);q=copy.deepcopy(r);q['pledge_cents']+=1;b['routes'].append(q)
 assert analyze(b)==analyze(request())

def test_signed_void_and_partition_validation():
 b=request();r=copy.deepcopy(b['routes'][0]);r.update(revision=20,known=20,void=True);b['routes'].append(r);assert analyze(b)==oracle(b)
 b=request();r=copy.deepcopy(b['routes'][0]);r.update(revision=20,known=20);r['windows'][0]['until_day']=9;b['routes'].append(r)
 with pytest.raises(ValueError):analyze(b)

def test_generated_bounded_oracle():
 rng=random.Random(6812)
 for case in range(14):
  b=dict(as_of=4,obligations=[],facilities=[dict(id='A',cap=rng.randint(3,10)),dict(id='B',cap=rng.randint(3,10))],collateral=[dict(id='X',cap=rng.randint(4,12)),dict(id='Y',cap=rng.randint(4,12))],routes=[],proposals=[])
  for i in range(3):
   cents=rng.randint(1,5);b['obligations'].append(dict(id=f'O{i}',cents=cents,pay_day=i,repaid_day=6+i))
   for j in range(2):
    b['routes'].append(dict(id=f'R{i}-{j}',revision=1,known=1,signed=True,void=False,obligation=f'O{i}',facility=rng.choice(['A','B']),pledge_cents=cents+1,windows=[dict(from_day=i,until_day=4,pool=rng.choice(['X','Y'])),dict(from_day=4,until_day=6+i,pool=rng.choice(['X','Y']))]))
  b['proposals']=[dict(id='cash',cost=1,facility_delta={'A':5,'B':5},collateral_delta={},routes=[]),dict(id='pledge',cost=2,facility_delta={},collateral_delta={'X':6,'Y':6},routes=[])]
  assert analyze(b)==oracle(b),case

def test_cli_json_contract():
 result=subprocess.run([sys.executable,'funding.py','data/request.json'],text=True,capture_output=True,timeout=30)
 assert result.returncode==0 and json.loads(result.stdout)==analyze(request())
