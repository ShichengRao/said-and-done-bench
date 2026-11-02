import copy,hashlib,itertools,json,subprocess,sys
from pathlib import Path
import pytest
import release_audit as a

def _trusted_support(filename):
    # Keep evaluator helpers out of the candidate's Python import namespace.
    import importlib.util
    source=Path(__file__).resolve().with_name(filename)
    spec=importlib.util.spec_from_file_location('_trusted_support_'+source.stem,source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

envelope=_trusted_support('fixture_support.py').envelope

def fixture():return json.loads((Path(__file__).parent/'original/data/input.json').read_text())
def scoped_fixture(data,scope):
 # Scope reduction must preserve the public proposal schema: a whole owner
 # proposal is retained only when every withdrawn operation remains scoped.
 result=copy.deepcopy(data);result['scope']=list(scope);allowed=set(scope)
 result['owner_requests']=[q for q in result['owner_requests'] if set(q['withdraw'])<=allowed]
 return result

def selected(d):
 out={}
 for e in d['operations']:
  b=e['signed']
  if b['id'] not in out or b['revision']>out[b['id']]['revision']:out[b['id']]=b
 return out

def lawful(order,ops,initial):
 state=dict(initial);positions={k:i for i,k in enumerate(order)}
 if any(ops[x]['respond']<=ops[y]['invoke'] and positions[x]>positions[y] for x in order for y in order if x!=y):return False
 for k in order:
  o=ops[k];ok=all(state[r]==v for r,v in o['expected'].items())
  if ok!=o['success']:return False
  if ok:state.update(o['writes'])
 return True

def test_canonical_independent_permutations_all_proper_subsets():
 d=fixture();ops=selected(d);out=a.audit(d);assert not any(lawful(order,ops,d['initial']) for order in itertools.permutations(d['scope']))
 for omitted in d['scope']:
  subset=[k for k in d['scope'] if k!=omitted];assert any(lawful(order,ops,d['initial']) for order in itertools.permutations(subset))
 assert not out['certifiable'] and out['minimal_core']==d['scope'] and all(out['projections'].values()) and len(out['history']['max_prefix'])==5
 assert out['owner_plan']['requests']==['withdraw-0'] and lawful(out['owner_plan']['history'],ops,d['initial'])
 # Independent enumeration of every prefix permutation derives certificate states.
 states=set()
 for n in range(7):
  for order in itertools.permutations(d['scope'],n):
   if lawful(order,ops,d['initial']):
    current=dict(d['initial'])
    for k in order:
     if ops[k]['success']:current.update(ops[k]['writes'])
    states.add(json.dumps([sorted(order),current],sort_keys=True,separators=(',',':')))
 enc=json.dumps(sorted(states),sort_keys=True,separators=(',',':')).encode();assert out['history']['reachable_count']==len(states) and out['history']['reachable_sha256']==hashlib.sha256(enc).hexdigest()

def test_changed_observed_fence_feasible_counterfactual():
 d=fixture()
 for i,e in enumerate(d['operations']):
  if e['signed']['id']=='o0' and e['signed']['revision']==2:
   body=copy.deepcopy(e['signed']);body['expected']['s5']=1;d['operations'][i]=envelope(body,['k0'])
 out=a.audit(d);assert out['certifiable'] and out['history']['history']==['o5','o4','o3','o2','o1','o0'] and out['blocker'] is None

def test_realtime_constraints_override_value_order():
 d=scoped_fixture(fixture(),['o0','o1'])
 for i,e in enumerate(d['operations']):
  b=copy.deepcopy(e['signed'])
  if b['revision']==2:
   if b['id']=='o0':b.update(invoke=1,respond=2)
   if b['id']=='o1':b.update(invoke=3,respond=4)
   d['operations'][i]=envelope(b,['k0'])
 out=a.audit(d);assert not out['certifiable'] and out['minimal_core']==['o0','o1']

def test_failed_operations_and_read_only_results():
 d=scoped_fixture(fixture(),['o0','o1'])
 for i,e in enumerate(d['operations']):
  b=copy.deepcopy(e['signed'])
  if b['revision']==2 and b['id']=='o1':b.update(success=False,writes={});d['operations'][i]=envelope(b,['k0'])
 x=a.audit(d);assert x['certifiable'] and x['history']['history']==['o0','o1']
 d=scoped_fixture(d,['o1']);x=a.audit(d);assert not x['certifiable']

def test_grants_do_not_combine_and_signatures_are_verified():
 for mode in ['partial','signature','missing']:
  d=scoped_fixture(fixture(),['o0'])
  if mode=='partial':
   d['grants']=[g for g in d['grants'] if g['id']!='g0'];base=fixture()['grants'][0];d['grants']+=[{**base,'id':'partial-a','resources':['s0']},{**base,'id':'partial-b','resources':['s5']}]
  elif mode=='signature':
   for e in d['operations']:
    if e['signed']['id']=='o0' and e['signed']['revision']==2:e['signatures'][0]['sig']='00'
  else:d['operations']=[e for e in d['operations'] if e['signed']['id']!='o0']
  out=a.audit(d);assert not out['certifiable'] and out['invalid']==[dict(id='o0',reason={'partial':'grant','signature':'signature','missing':'missing'}[mode])]

def test_revision_order_conflicts_and_input_preservation():
 d=fixture();expected=a.audit(d);old=copy.deepcopy(d);d['operations'].reverse();d['grants'].reverse();assert a.audit(d)==expected and old==fixture()
 b=copy.deepcopy(d['operations'][0]);b['signed']['success']=not b['signed']['success'];d['operations'].append(b)
 with pytest.raises(ValueError):a.audit(d)

def test_generated_small_scopes_against_permutation_oracle():
 d=fixture();ops=selected(d)
 for n in range(1,6):
  subset=scoped_fixture(d,sorted(ops)[:n]);out=a.audit(subset);legal=[list(p) for p in itertools.permutations(subset['scope']) if lawful(p,ops,d['initial'])];assert out['certifiable']==bool(legal) and out['history']['history']==min(legal)

def test_cli(tmp_path):
 d=fixture();p=tmp_path/'data.json';p.write_text(json.dumps(d));result=subprocess.run([sys.executable,a.__file__,str(p)],capture_output=True,text=True);assert result.returncode==0 and json.loads(result.stdout)==a.audit(d)
