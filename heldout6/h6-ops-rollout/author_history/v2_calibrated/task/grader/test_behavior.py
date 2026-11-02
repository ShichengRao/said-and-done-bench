import copy,json
from concurrent.futures import ThreadPoolExecutor
import pytest
import controller as c

def config():
 return dict(nodes={n:dict(rack='r',zone=z,capacity=1) for n,z in [('a','x'),('b','y'),('c','x'),('d','y')]},rack_capacity={'r':4},services={'svc':dict(size=1,min_ready=2,min_zones=2)},initial={'a':dict(service='svc',image='old'),'b':dict(service='svc',image='old'),'c':None,'d':None},max_inflight=3)
def plan():
 actions=[dict(id='c',depends=[],op='start',node='c',service='svc',image='new'),dict(id='d',depends=[],op='start',node='d',service='svc',image='new'),dict(id='x',depends=['c'],op='stop',node='a',service='svc',image='old'),dict(id='y',depends=['d'],op='stop',node='b',service='svc',image='old')]
 return dict(epoch=1,observed=config()['initial'],actions=actions,target={'a':None,'b':None,'c':dict(service='svc',image='new'),'d':dict(service='svc',image='new')})
def call(p,kind,**args):
 version=c.inspect(p)['version'];return c.apply(p,dict(id='q'+str(version),expected_version=version,kind=kind,**args))
def setup(tmp_path):
 p=str(tmp_path/'db');c.initialize(p,config());call(p,'install',**plan());return p

def test_parallel_dispatch_and_out_of_order_receipts(tmp_path):
 p=setup(tmp_path);x=call(p,'dispatch');assert x['created']==['1:c:1','1:d:1'] and x['observed']==config()['initial'] and x['done']==[]
 call(p,'receipt',receipts=[dict(token='1:d:1',success=True)]);x=call(p,'dispatch');assert x['created']==['1:y:1']
 call(p,'receipt',receipts=[dict(token='1:y:1',success=True),dict(token='1:c:1',success=True)]);x=call(p,'dispatch');assert x['created']==['1:x:1'];x=call(p,'receipt',receipts=[dict(token='1:x:1',success=True)]);assert x['observed']==plan()['target'] and x['done']==['c','d','x','y']

def test_independent_failure_and_retry_tokens(tmp_path):
 p=setup(tmp_path);call(p,'dispatch');call(p,'receipt',receipts=[dict(token='1:c:1',success=False),dict(token='1:d:1',success=True)]);x=call(p,'dispatch');assert x['created']==['1:c:2','1:y:1'];old=c.inspect(p)
 with pytest.raises(ValueError):call(p,'receipt',receipts=[dict(token='1:c:1',success=True)])
 assert c.inspect(p)==old

def test_full_success_is_not_sufficient_for_dispatch(tmp_path):
 cfg=config();cfg['services']['svc']['min_ready']=1;cfg['services']['svc']['min_zones']=1;cfg['initial']={'a':dict(service='svc',image='old'),'b':None,'c':None,'d':None};p=str(tmp_path/'db');c.initialize(p,cfg)
 actions=[dict(id='a-start',depends=[],op='start',node='c',service='svc',image='new'),dict(id='b-stop',depends=[],op='stop',node='a',service='svc',image='old')];target={**cfg['initial'],'a':None,'c':dict(service='svc',image='new')};call(p,'install',epoch=1,observed=cfg['initial'],actions=actions,target=target)
 x=call(p,'dispatch');assert x['created']==['1:a-start:1']

def test_reservations_do_not_spend_unacknowledged_stop_capacity(tmp_path):
 cfg=config();cfg['rack_capacity']['r']=3;p=str(tmp_path/'db');c.initialize(p,cfg);call(p,'install',**plan());x=call(p,'dispatch');assert x['created']==['1:c:1'];call(p,'receipt',receipts=[dict(token='1:c:1',success=True)]);x=call(p,'dispatch');assert x['created']==['1:x:1'];call(p,'receipt',receipts=[dict(token='1:x:1',success=True)]);assert call(p,'dispatch')['created']==['1:d:1']

def test_install_supersedes_pending_and_old_receipt_cannot_mutate(tmp_path):
 p=setup(tmp_path);call(p,'dispatch');q=plan();q['epoch']=2;call(p,'install',**q);x=call(p,'receipt',receipts=[dict(token='1:c:1',success=True)]);assert x['receipts'][0]['disposition']=='stale' and x['observed']==config()['initial'];assert call(p,'dispatch')['created']==['2:c:1','2:d:1']

def test_receipt_batch_rollback_on_late_conflict(tmp_path):
 p=setup(tmp_path);call(p,'dispatch');call(p,'receipt',receipts=[dict(token='1:c:1',success=False)]);old=c.inspect(p)
 with pytest.raises(ValueError):call(p,'receipt',receipts=[dict(token='1:d:1',success=True),dict(token='1:c:1',success=True)])
 assert c.inspect(p)==old

def test_replay_before_cas_and_request_payload_binding(tmp_path):
 p=setup(tmp_path);req=dict(id='retry',expected_version=1,kind='dispatch');x=c.apply(p,req);call(p,'receipt',receipts=[]);assert c.apply(p,req)==x
 with pytest.raises(ValueError):c.apply(p,{**req,'kind':'receipt','receipts':[]})

def test_plan_cycles_terminal_identity_and_precondition_failures(tmp_path):
 for kind in ['cycle','target','identity']:
  root=tmp_path/kind;root.mkdir();p=setup(root);q=plan();q['epoch']=2
  if kind=='cycle':q['actions'][0]['depends']=['x']
  if kind=='target':q['target']['a']=dict(service='svc',image='new')
  if kind=='identity':q['actions'][-1]['image']='wrong'
  old=c.inspect(p)
  with pytest.raises(ValueError):call(p,'install',**q)
  assert c.inspect(p)==old

def test_projection_into_zones_and_node_lock(tmp_path):
 p=setup(tmp_path);call(p,'dispatch');x=call(p,'dispatch');assert x['created']==[] and len(x['pending'])==2
 call(p,'receipt',receipts=[dict(token='1:c:1',success=True)]);x=call(p,'dispatch');assert x['created']==['1:x:1']

def test_duplicate_receipts_and_inputs_unchanged(tmp_path):
 p=setup(tmp_path);call(p,'dispatch');rs=[dict(token='1:c:1',success=True)]*2;old=copy.deepcopy(rs);x=call(p,'receipt',receipts=rs);assert [r['disposition'] for r in x['receipts']]==['applied','replayed'] and rs==old

def test_concurrent_dispatch_cas_and_restart(tmp_path):
 p=setup(tmp_path)
 def work(i):
  try:return c.apply(p,dict(id=str(i),expected_version=1,kind='dispatch'))
  except ValueError:return None
 with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(work,[1,2]))
 assert sum(x is not None for x in out)==1 and len(c.inspect(p)['pending'])==2
 assert c.initialize(p,config())['version']==2

def test_generated_receipt_orders_have_same_terminal_state(tmp_path):
 import itertools
 for index,order in enumerate(itertools.permutations(['c','d'])):
  root=tmp_path/str(index);root.mkdir();p=setup(root);call(p,'dispatch')
  for a in order:call(p,'receipt',receipts=[dict(token='1:'+a+':1',success=True)])
  x=call(p,'dispatch');assert x['created']==['1:x:1','1:y:1']
  for token in reversed(x['created']):call(p,'receipt',receipts=[dict(token=token,success=True)])
  assert c.inspect(p)['observed']==plan()['target']


def test_fresh_process_inspect_and_original_response(tmp_path):
 import subprocess,sys
 p=setup(tmp_path);q=dict(id='durable',expected_version=1,kind='dispatch')
 response=c.apply(p,q)
 c.apply(p,dict(id='later',expected_version=2,kind='receipt',receipts=[]))
 request=tmp_path/'request.json';request.write_text(json.dumps(q))
 script="import json,sys,controller as m; p=sys.argv[1]; q=json.load(open(sys.argv[2])); print(json.dumps({'current':m.inspect(p),'replay':m.apply(p,q)}))"
 child=subprocess.run([sys.executable,'-c',script,p,str(request)],capture_output=True,text=True,timeout=15)
 assert child.returncode==0,child.stderr
 out=json.loads(child.stdout);assert out['current']==c.inspect(p) and out['replay']==response

def test_synchronized_separate_process_cas(tmp_path):
 import subprocess,sys,time
 p=setup(tmp_path);q=dict(id='durable',expected_version=1,kind='dispatch')
 request=tmp_path/'request.json';request.write_text(json.dumps(q));gate=tmp_path/'gate'
 script="""import json,sys,time,pathlib,controller as m
p,request,ready,gate,identity=sys.argv[1:]
q=json.load(open(request));q['id']=identity
pathlib.Path(ready).touch()
while not pathlib.Path(gate).exists():time.sleep(.005)
try: result=m.apply(p,q)['version']
except ValueError: result=None
print(json.dumps(result))
"""
 children=[subprocess.Popen([sys.executable,'-c',script,p,str(request),str(tmp_path/('ready'+str(i))),str(gate),'process'+str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for i in range(2)]
 deadline=time.monotonic()+10
 while not all((tmp_path/('ready'+str(i))).exists() for i in range(2)) and time.monotonic()<deadline:time.sleep(.005)
 gate.touch();outputs=[child.communicate(timeout=15) for child in children]
 assert all(child.returncode==0 for child in children),outputs
 results=[json.loads(out) for out,err in outputs];assert results.count(2)==1 and results.count(None)==1
 assert c.inspect(p)['version']==2


def _independent_inventory_safe(cfg,inventory):
 if set(inventory)!=set(cfg['nodes']):return False
 for node,value in inventory.items():
  if value is not None and (value['service'] not in cfg['services'] or cfg['services'][value['service']]['size']>cfg['nodes'][node]['capacity']):return False
 for rack,capacity in cfg['rack_capacity'].items():
  if sum(cfg['services'][value['service']]['size'] for node,value in inventory.items() if value is not None and cfg['nodes'][node]['rack']==rack)>capacity:return False
 for service,requirements in cfg['services'].items():
  placed=[node for node,value in inventory.items() if value is not None and value['service']==service]
  if len(placed)<requirements['min_ready'] or len({cfg['nodes'][node]['zone'] for node in placed})<requirements['min_zones']:return False
 return True


def _independent_apply_action(cfg,inventory,action):
 node=action['node'];identity={'service':action['service'],'image':action['image']}
 if node not in inventory:return None
 if action['op']=='start':
  if inventory[node] is not None:return None
  value=identity
 elif action['op']=='stop':
  if inventory[node]!=identity:return None
  value=None
 else:return None
 result={**inventory,node:value}
 return result if _independent_inventory_safe(cfg,result) else None


def _bounded_install_orders(cfg,observed,actions,target):
 """Enumerate complete permutations, independent of the controller's state search."""
 import itertools
 if not _independent_inventory_safe(cfg,observed) or not _independent_inventory_safe(cfg,target):return []
 by_id={a['id']:a for a in actions};answers=[]
 if len(by_id)!=len(actions):return []
 for order in itertools.permutations(sorted(by_id)):
  inventory=copy.deepcopy(observed);finished=set()
  for identity in order:
   action=by_id[identity]
   if not set(action['depends'])<=finished:break
   inventory=_independent_apply_action(cfg,inventory,action)
   if inventory is None:break
   finished.add(identity)
  else:
   if inventory==target:answers.append(order)
 return answers


def _greedy_dead_end_case():
 cfg=dict(nodes={n:dict(rack='r',zone='z',capacity=1) for n in 'abc'},rack_capacity={'r':2},services={'svc':dict(size=1,min_ready=1,min_zones=1)},initial={'a':dict(service='svc',image='old'),'b':None,'c':None},max_inflight=3)
 actions=[dict(id='a-extra',depends=[],op='start',node='b',service='svc',image='new'),dict(id='b-replacement',depends=[],op='start',node='c',service='svc',image='new'),dict(id='c-retire',depends=['b-replacement'],op='stop',node='a',service='svc',image='old')]
 target={'a':None,'b':dict(service='svc',image='new'),'c':dict(service='svc',image='new')}
 return cfg,actions,target


def test_install_explores_alternate_order_after_safe_greedy_dead_end(tmp_path):
 cfg,actions,target=_greedy_dead_end_case()
 assert _bounded_install_orders(cfg,cfg['initial'],actions,target)==[('b-replacement','c-retire','a-extra')]
 first=_independent_apply_action(cfg,cfg['initial'],actions[0]);assert first is not None
 # The lexicographically first action is individually safe, but consumes the
 # spare rack slot; the replacement cannot start and retirement is not enabled.
 assert _independent_apply_action(cfg,first,actions[1]) is None
 assert not set(actions[2]['depends'])<={'a-extra'}
 p=str(tmp_path/'alternate-order.db');c.initialize(p,cfg)
 result=c.apply(p,dict(id='install',expected_version=0,kind='install',epoch=1,observed=cfg['initial'],actions=actions,target=target))
 assert result['installed'] and result['observed']==cfg['initial'] and result['target']==target and result['done']==[]


def _bounded_install_examples():
 import random
 rng=random.Random(67341);examples=[]
 for capacity in [2,3]:
  for dependency in ['normal','extra-before-replacement','extra-after-retire','cycle','free']:
   cfg,actions,target=_greedy_dead_end_case();cfg['rack_capacity']['r']=capacity
   if dependency=='extra-before-replacement':actions[1]['depends']=['a-extra']
   if dependency=='extra-after-retire':actions[0]['depends']=['c-retire']
   if dependency=='cycle':actions[1]['depends']=['c-retire']
   if dependency=='free':actions[2]['depends']=[]
   examples.append((cfg,actions,target))
 for case in range(20):
  cfg,actions,target=_greedy_dead_end_case();cfg['nodes']['d']=dict(rack='r',zone='other',capacity=1);cfg['initial']['d']=None;target['d']=dict(service='svc',image='new')
  cfg['rack_capacity']['r']=rng.choice([3,4]);actions.append(dict(id='d-extra',depends=[],op='start',node='d',service='svc',image='new'))
  order=rng.sample([a['id'] for a in actions],len(actions));rank={name:i for i,name in enumerate(order)}
  for action in actions:action['depends']=sorted(other['id'] for other in actions if rank[other['id']]<rank[action['id']] and rng.randrange(3)==0)
  if case%5==0:actions[2]['image']='nonexistent'
  if case%7==0:target['b']=dict(service='svc',image='wrong-target')
  rng.shuffle(actions);examples.append((cfg,actions,target))
 return examples


def test_install_matches_independent_bounded_DAG_schedule_enumeration(tmp_path):
 examples=_bounded_install_examples()
 accepted=rejected=0
 for index,(cfg,actions,target) in enumerate(examples):
  expected=bool(_bounded_install_orders(cfg,cfg['initial'],actions,target));accepted+=expected;rejected+=not expected
  p=str(tmp_path/('bounded-'+str(index)+'.db'));c.initialize(p,cfg);before=c.inspect(p)
  request=dict(id='install',expected_version=0,kind='install',epoch=1,observed=copy.deepcopy(cfg['initial']),actions=copy.deepcopy(actions),target=copy.deepcopy(target));original=copy.deepcopy(request)
  if expected:
   result=c.apply(p,request);assert result['installed'] and result['version']==1 and result['target']==target
  else:
   with pytest.raises(ValueError):c.apply(p,request)
   assert c.inspect(p)==before
  assert request==original
 assert accepted>=5 and rejected>=5


def _literal_oracle():
 import importlib.util
 from pathlib import Path
 source=Path(__file__).resolve().with_name('oracle.py')
 spec=importlib.util.spec_from_file_location('_trusted_rollout_oracle',source)
 result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
 return result


def _production():
 from pathlib import Path
 return json.loads(Path('data/input.json').read_text())


def _assert_oracle_summary(actual,expected,state):
 # SPEC leaves pending.action's representation open. Normalize only this
 # cross-implementation comparison, after validating any complete action payload.
 normalized=copy.deepcopy(actual)
 for entry in normalized['pending'].values():
  action=entry['action']
  if isinstance(action,dict):
   epoch=expected['epoch']
   if epoch==state['epoch']:declared=state['actions']
   else:
    # A saved response may belong to an older installed epoch than current state.
    payloads=[json.loads(payload) for payload,response in state['requests'].values()]
    installs=[q for q in payloads if q.get('kind')=='install' and q.get('epoch')==epoch]
    assert len(installs)==1,'missing installed action declaration for response epoch'
    declared={a['id']:a for a in installs[0]['actions']}
   identity=action.get('id')
   assert isinstance(identity,str) and identity in declared,'unknown pending action identity'
   installed=declared[identity]
   assert all(isinstance(action.get(k),str) and action[k]==installed[k]
              for k in ('id','op','node','service','image')),'contradictory pending action fields'
   depends=action.get('depends')
   assert isinstance(depends,(list,tuple)) and all(isinstance(k,str) for k in depends),'invalid pending dependency IDs'
   assert set(depends)==set(installed['depends']),'contradictory pending dependencies'
   entry['action']=identity
 assert normalized==expected


def _compare_request(path,state,request,oracle):
 before=c.inspect(path);original=copy.deepcopy(request)
 try:after,expected=oracle.transition(state,copy.deepcopy(request))
 except ValueError:
  with pytest.raises(ValueError):c.apply(path,request)
  assert c.inspect(path)==before
  assert request==original
  return state,False
 actual=c.apply(path,request)
 _assert_oracle_summary(actual,expected,after)
 _assert_oracle_summary(c.inspect(path),oracle.summary(after),after)
 assert request==original
 return after,True


def test_supplied_production_trace_matches_literal_oracle(tmp_path):
 data=_production();oracle=_literal_oracle();p=str(tmp_path/'production.db')
 state=oracle.initialize(data['configuration'])
 assert c.initialize(p,copy.deepcopy(data['configuration']))==oracle.summary(state)
 requests=[dict(id='install-production',expected_version=0,kind='install',**data['install']),*data['trace']]
 rejected=[]
 for request in requests:
  state,accepted=_compare_request(p,state,request,oracle)
  if not accepted:rejected.append(request['id'])
 assert rejected==['conflicting-old-success']
 assert state['observed']==data['install']['target'] and state['pending']=={}
 assert state['done']==sorted(action['id'] for action in data['install']['actions'])
 assert state['version']==13


def test_production_completion_cut_and_subset_safety_proof():
 data=_production();oracle=_literal_oracle();cfg=data['configuration'];plan=data['install']
 actions={a['id']:a for a in plan['actions']};observed=plan['observed']
 orders=oracle.schedules(cfg,observed,actions,plan['target'])
 assert len(orders)==40
 counts={}
 for identity in ['a-expand-west','b-copy-east','c-copy-west','d-expand-east']:
  after=oracle.effect(observed,actions[identity]);assert oracle.safe(cfg,after)
  counts[identity]=len(oracle.schedules(cfg,after,actions,plan['target'],[identity]))
 assert list(counts.values())==[0,10,20,10]
 projected=observed
 for identity in ['b-copy-east','c-copy-west']:projected=oracle.effect(projected,actions[identity])
 assert len(oracle.schedules(cfg,projected,actions,plan['target'],['b-copy-east','c-copy-west']))==6
 assert oracle.safe(cfg,oracle.effect(projected,actions['e-retire-east']))
 assert not oracle.safe(cfg,oracle.effect(observed,actions['e-retire-east']))
 # Previously pending B and a new D consume six physical units against four.
 after_c=oracle.effect(observed,actions['c-copy-west'])
 both=oracle.effect(oracle.effect(after_c,actions['b-copy-east']),actions['d-expand-east'])
 assert not oracle.safe(cfg,both)
 assert oracle.safe(cfg,oracle.effect(after_c,actions['d-expand-east']))


def test_generated_rollouts_match_literal_request_oracle(tmp_path):
 import random
 data=_production();oracle=_literal_oracle();rng=random.Random(60821)
 for index in range(12):
  cfg=copy.deepcopy(data['configuration']);plan=copy.deepcopy(data['install'])
  cfg['rack_capacity']['west']=4 if index%2 else 6
  cfg['rack_capacity']['east']=4 if index%3 else 6
  cfg['max_inflight']=index%3+1
  # Remove or retain the real rollout prerequisite; no unknown references.
  if index%4==0:plan['actions'][-1]['depends']=[]
  names=[action['id'] for action in plan['actions']];renamed=rng.sample(names,len(names));mapping=dict(zip(names,renamed))
  for action in plan['actions']:
   action['id']=mapping[action['id']];action['depends']=[mapping[d] for d in action['depends']]
  rng.shuffle(plan['actions'])
  root=tmp_path/str(index);root.mkdir();path=str(root/'generated.db')
  state=oracle.initialize(cfg);c.initialize(path,cfg)
  state,_=_compare_request(path,state,dict(id='install',expected_version=0,kind='install',**plan),oracle)
  failed_once=False
  for step in range(40):
   if len(state['done'])==len(plan['actions']):break
   state,_=_compare_request(path,state,dict(id='dispatch-'+str(step),expected_version=state['version'],kind='dispatch'),oracle)
   assert state['pending'],'completion-preserving dispatch stranded the rollout'
   token=sorted(state['pending'],reverse=bool(step%2))[0]
   success=failed_once or step!=1
   if not success:failed_once=True
   state,_=_compare_request(path,state,dict(id='receipt-'+str(step),expected_version=state['version'],kind='receipt',receipts=[dict(token=token,success=success)]),oracle)
  else:raise AssertionError('bounded generated trace did not complete')
  assert state['observed']==plan['target'] and not state['pending']


def test_total_window_counts_preexisting_pending_commands(tmp_path):
 data=_production();oracle=_literal_oracle();cfg=data['configuration'];cfg['rack_capacity']={'west':6,'east':6}
 path=str(tmp_path/'window.db');state=oracle.initialize(cfg);c.initialize(path,cfg)
 state,_=_compare_request(path,state,dict(id='install',expected_version=0,kind='install',**data['install']),oracle)
 state,_=_compare_request(path,state,dict(id='first',expected_version=1,kind='dispatch'),oracle)
 assert len(state['pending'])==3
 before=copy.deepcopy(state['pending'])
 state,_=_compare_request(path,state,dict(id='still-full',expected_version=2,kind='dispatch'),oracle)
 assert state['pending']==before
 state,_=_compare_request(path,state,dict(id='partial',expected_version=3,kind='receipt',receipts=[dict(token='1:c-copy-west:1',success=True)]),oracle)
 state,_=_compare_request(path,state,dict(id='one-space',expected_version=4,kind='dispatch'),oracle)
 assert len(state['pending'])==3 and '1:d-expand-east:1' in state['pending']
