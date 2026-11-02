import copy,hashlib,json
from concurrent.futures import ThreadPoolExecutor
import pytest
import release_gate as g
from fixture_support import fleet,envelope,refresh

def setup(tmp_path,seed=0):
 p=str(tmp_path/'db');a,q=fleet(seed);g.initialize(p,a);return p,a,q

def test_canonical_three_repo_diamond_atomic_install(tmp_path):
 p,a,q=setup(tmp_path);x=g.install(p,q);assert [(r['repo'],r['path']) for r in x['installed']]==[('app','apps/0/api'),('base','apps/0/worker'),('lib','apps/0/api')];assert all(r['root_version']==2 and r['snapshot_version']==5 for r in x['repositories'].values())
 assert g.inspect(p)['version']==1 and all('unused' not in r['roles'] for r in x['repositories'].values())

def test_late_dependency_bytes_fail_without_advancing_any_trust(tmp_path):
 p,a,q=setup(tmp_path);old=g.inspect(p);q['bundles']['base']['artifacts']['apps/0/worker']='corrupt'
 with pytest.raises(ValueError):g.install(p,q)
 assert g.inspect(p)==old

def test_diamond_pin_conflict_and_unknown_repository(tmp_path):
 for mode in ['pin','repo']:
  folder=tmp_path/mode;folder.mkdir();p,a,q=setup(folder);b=q['bundles']['app'];body=b['metadata']['packages']['signed'];dep=body['targets']['apps/0/api']['dependencies'][1]
  if mode=='pin':dep['sha256']='0'*64
  else:dep['repo']='missing'
  b['metadata']['packages']=envelope(body,['k2']);refresh(b)
  with pytest.raises(ValueError):g.install(p,q)
  assert g.inspect(p)['version']==0

def test_exact_replay_before_cas_and_payload_binding(tmp_path):
 p,a,q=setup(tmp_path);x=g.install(p,q);assert g.install(p,copy.deepcopy(q))==x
 bad=copy.deepcopy(q);bad['expected_version']=1
 with pytest.raises(ValueError):g.install(p,bad)
 assert g.initialize(p,a)['version']==1

def test_root_requires_old_and_new_thresholds(tmp_path):
 for kids in [['k1','k2'],['k0','k1'],['k1','k1','k2']]:
  folder=tmp_path/str(len(list(tmp_path.iterdir())));folder.mkdir();p,a,q=setup(folder);e=q['bundles']['lib']['roots'][0];q['bundles']['lib']['roots']=[envelope(e['signed'],kids)]
  with pytest.raises(ValueError):g.install(p,q)

def test_rollback_of_one_repository_rejects_whole_install(tmp_path):
 p,a,q=setup(tmp_path);g.install(p,q);later=copy.deepcopy(q);later.update(id='next',expected_version=1)
 for b in later['bundles'].values():b['roots']=[]
 b=later['bundles']['lib'];b['snapshot']['signed']['version']=4;refresh(b);old=g.inspect(p)
 with pytest.raises(ValueError):g.install(p,later)
 assert g.inspect(p)==old

def test_dependency_cycle_and_role_cycle(tmp_path):
 for mode in ['artifact','role']:
  folder=tmp_path/mode;folder.mkdir();p,a,q=setup(folder)
  if mode=='artifact':
   b=q['bundles']['base'];body=b['metadata']['packages']['signed'];body['targets']['apps/0/worker']['dependencies']=[q['requested'][0]];b['metadata']['packages']=envelope(body,['k2'])
  else:
   b=q['bundles']['app'];body=b['metadata']['team']['signed'];body['delegations'][0].update(name='team',keyids=['k1']);b['metadata']['team']=envelope(body,['k1'])
  refresh(b)
  with pytest.raises(ValueError):g.install(p,q)

def test_terminating_miss_propagates_to_ancestor(tmp_path):
 p,a,q=setup(tmp_path);b=q['bundles']['app'];body=b['metadata']['packages']['signed'];saved=copy.deepcopy(body);body['targets']={};b['metadata']['packages']=envelope(body,['k2']);saved['role']='fallback';b['metadata']['fallback']=envelope(saved,['k2']);top=b['metadata']['targets']['signed'];top['delegations'].append(dict(name='fallback',paths=['apps/*'],keyids=['k2'],threshold=1,terminating=False));b['metadata']['targets']=envelope(top,['k2']);refresh(b)
 with pytest.raises(ValueError):g.install(p,q)

def test_metadata_envelope_pin_and_role_equivocation(tmp_path):
 p,a,q=setup(tmp_path);bad=copy.deepcopy(q);bad['bundles']['base']['metadata']['packages']['signatures'].reverse();bad['bundles']['base']['metadata']['packages']['signatures'].append(copy.deepcopy(bad['bundles']['base']['metadata']['packages']['signatures'][0]))
 with pytest.raises(ValueError):g.install(p,bad)
 g.install(p,q);later=copy.deepcopy(q);later.update(id='next',expected_version=1)
 for b in later['bundles'].values():b['roots']=[];b['snapshot']['signed']['version']+=1;refresh(b)
 b=later['bundles']['base'];body=b['metadata']['packages']['signed'];body['expires']+=1;b['metadata']['packages']=envelope(body,['k2']);refresh(b)
 with pytest.raises(ValueError):g.install(p,later)

def test_independent_repo_namespace_unused_bundle_and_input_preservation(tmp_path):
 p,a,q=setup(tmp_path);q['bundles']['untrusted']={'broken':True};old=copy.deepcopy(q);x=g.install(p,q);assert q==old and 'untrusted' not in x['repositories']

def test_concurrent_cas_one_install(tmp_path):
 p,a,q=setup(tmp_path)
 def work(i):
  try:return g.install(p,{**q,'id':str(i)})['version']
  except ValueError:return None
 with ThreadPoolExecutor(max_workers=2) as pool:xs=list(pool.map(work,[1,2]))
 assert xs.count(1)==1 and xs.count(None)==1

def test_generated_names_and_dependency_order_invariance(tmp_path):
 for seed in range(4):
  folder=tmp_path/str(seed);folder.mkdir();p,a,q=setup(folder,seed);body=q['bundles']['app']['metadata']['packages']['signed'];body['targets']['apps/'+str(seed)+'/api']['dependencies'].reverse();q['bundles']['app']['metadata']['packages']=envelope(body,['k2']);refresh(q['bundles']['app']);x=g.install(p,q);assert len(x['installed'])==3 and x['version']==1


def test_fresh_process_inspect_and_original_response(tmp_path):
 import subprocess,sys
 p,anchors,q=setup(tmp_path)
 response=g.install(p,q)
 later=copy.deepcopy(q);later.update(id='later',expected_version=1)
 for b in later['bundles'].values():b['roots']=[]
 g.install(p,later)
 request=tmp_path/'request.json';request.write_text(json.dumps(q))
 script="import json,sys,release_gate as m; p=sys.argv[1]; q=json.load(open(sys.argv[2])); print(json.dumps({'current':m.inspect(p),'replay':m.install(p,q)}))"
 child=subprocess.run([sys.executable,'-c',script,p,str(request)],capture_output=True,text=True,timeout=15)
 assert child.returncode==0,child.stderr
 out=json.loads(child.stdout);assert out['current']==g.inspect(p) and out['replay']==response

def test_synchronized_separate_process_cas(tmp_path):
 import subprocess,sys,time
 p,anchors,q=setup(tmp_path)
 request=tmp_path/'request.json';request.write_text(json.dumps(q));gate=tmp_path/'gate'
 script="""import json,sys,time,pathlib,release_gate as m
p,request,ready,gate,identity=sys.argv[1:]
q=json.load(open(request));q['id']=identity
pathlib.Path(ready).touch()
while not pathlib.Path(gate).exists():time.sleep(.005)
try: result=m.install(p,q)['version']
except ValueError: result=None
print(json.dumps(result))
"""
 children=[subprocess.Popen([sys.executable,'-c',script,p,str(request),str(tmp_path/('ready'+str(i))),str(gate),'process'+str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for i in range(2)]
 deadline=time.monotonic()+10
 while not all((tmp_path/('ready'+str(i))).exists() for i in range(2)) and time.monotonic()<deadline:time.sleep(.005)
 gate.touch();outputs=[child.communicate(timeout=15) for child in children]
 assert all(child.returncode==0 for child in children),outputs
 results=[json.loads(out) for out,err in outputs];assert results.count(1)==1 and results.count(None)==1
 assert g.inspect(p)['version']==1
