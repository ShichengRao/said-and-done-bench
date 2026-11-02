import copy,hashlib,itertools,json,subprocess,sys
from collections import deque
from pathlib import Path
import pytest
import planner as p

def production():return json.loads((Path(__file__).parent/'original/data/input.json').read_text())
def oracle(d,edges):
 # Independent full copy-state BFS: unlike the reference's stable-state expansion,
 # copying, ready and commit each enter the queue as distinct states.
 us=sorted(d['units']);ns=sorted(d['nodes']);start=(tuple(d['initial']['positions'][u] for u in us),tuple(d['initial']['images'][u] for u in us),None);queue=deque([start]);paths={start:[]};enc=[];goal=None;stable=0
 def valid(pos,shadow):
  occupied=list(pos)+([] if shadow is None else [shadow[1]])
  if len(set(occupied))!=len(occupied):return False
  costs={r:0 for r in d['rack_capacity']}
  for u,node in list(zip(us,pos))+([] if shadow is None else [(shadow[0],shadow[1])]):
   size=d['units'][u]['size']
   if size>d['nodes'][node]['capacity']:return False
   costs[d['nodes'][node]['rack']]+=size
  for group,policy in d['groups'].items():
   places=[pos[i] for i,u in enumerate(us) if d['units'][u]['group']==group]
   if len(places)<policy['quorum'] or len({d['nodes'][n]['zone'] for n in places})<policy['min_zones']:return False
  return all(costs[r]<=v for r,v in d['rack_capacity'].items())
 while queue:
  state=queue.popleft();pos,im,shadow=state;enc.append(json.dumps([dict(zip(us,pos)),dict(zip(us,im)),None if shadow is None else list(shadow)],sort_keys=True,separators=(',',':')));nexts=[]
  if shadow is None:
   stable+=1
   if dict(zip(us,pos))==d['target'] and all(x=='new' for x in im) and goal is None:goal=paths[state]
   for i,u in enumerate(us):
    for dest in ns:
     sh=(u,dest,'copying')
     if (pos[i],dest) in edges and valid(pos,sh):nexts.append((['start',u,dest],(pos,im,sh)))
  elif shadow[2]=='copying':nexts.append((['ready',shadow[0],shadow[1]],(pos,im,(shadow[0],shadow[1],'ready'))))
  else:
   i=us.index(shadow[0]);new=list(pos);new[i]=shadow[1];images=list(im);images[i]='new'
   if valid(new,None):nexts.append((['commit',shadow[0],shadow[1]],(tuple(new),tuple(images),None)))
  for action,nxt in sorted(nexts):
   if nxt not in paths:paths[nxt]=paths[state]+[action];queue.append(nxt)
 return dict(reachable_count=len(paths),stable_count=stable,reachable_sha256=hashlib.sha256(json.dumps(sorted(enc),sort_keys=True,separators=(',',':')).encode()).hexdigest(),plan=goal)

def test_canonical_full_transition_oracle():
 d=production();out=p.audit(d);edges={tuple(e) for e in out['active_links']};expected=oracle(d,edges)
 assert all(out[k]==v for k,v in expected.items());assert out['static_final_valid'] and not out['certifiable'] and out['reachable_count']==3591 and out['stable_count']==513
 assert out['owner_plan']['requests']==['edge-01'];counter=oracle(d,edges|{('n0','n1')});assert out['owner_plan']['plan']==counter['plan'] and len(counter['plan'])==33

def test_actual_owner_edge_enables_same_target_and_rules():
 d=production();d['links'].append(dict(id='actual-owner-grant',revision=1,source='n0',target='n1',enabled=True,valid_from=0,valid_to=20));out=p.audit(d);assert out['certifiable'] and out['blocker'] is None and out['owner_plan']['requests']==[]

def test_capacity_counts_copy_and_quorum_never_counts_shadow():
 d=production();d['rack_capacity']['r']=5;out=p.audit(d);assert out['reachable_count']==1 and out['owner_plan'] is None
 d=production();d['nodes']['n5']['capacity']=0;out=p.audit(d);assert out['reachable_count']==1

def test_revision_expiry_direction_and_conflicts():
 d=production();out=p.audit(d);d['links'].reverse();assert p.audit(d)==out
 r=copy.deepcopy(d['links'][0]);r.update(revision=2,enabled=False);d['links'].append(r);assert [r['source'],r['target']] not in p.audit(d)['active_links']
 d['links'].append({**r,'enabled':True})
 with pytest.raises(ValueError):p.audit(d)

def test_small_generated_graphs_against_full_oracle():
 base=production()
 for n in range(4):
  d=dict(at=1,nodes={f'n{i}':dict(rack='r',zone=str(i),capacity=1) for i in range(3)},rack_capacity={'r':3},groups={'g':dict(quorum=2,min_zones=2)},units={f'u{i}':dict(group='g',size=1,allowed_final=['n0','n1','n2']) for i in range(2)},initial={'positions':{'u0':'n0','u1':'n1'},'images':{'u0':'old','u1':'new'}},target={'u0':'n1','u1':'n0'},links=[],owner_requests=[])
  edges={(f'n{a}',f'n{b}') for a,b in [(0,2),(2,0),(1,2),(2,1)]+([(0,1)] if n&1 else [])+([(1,0)] if n&2 else [])}
  for i,(a,b) in enumerate(sorted(edges)):d['links'].append(dict(id=str(i),revision=1,source=a,target=b,enabled=True,valid_from=0,valid_to=2))
  out=p.audit(d);expected=oracle(d,edges);assert all(out[k]==v for k,v in expected.items())

def test_final_allowed_scope_does_not_restrict_staging():
 d=production();d['links'].append(dict(id='extra',revision=1,source='n0',target='n1',enabled=True,valid_from=0,valid_to=20))
 for u in d['units']:d['units'][u]['allowed_final']=[d['target'][u]]
 assert p.audit(d)['certifiable']
 d['units']['u0']['allowed_final']=[];assert not p.audit(d)['certifiable']

def test_input_preservation_and_cli(tmp_path):
 d=production();old=copy.deepcopy(d);out=p.audit(d);assert d==old;f=tmp_path/'input.json';f.write_text(json.dumps(d));r=subprocess.run([sys.executable,p.__file__,str(f)],capture_output=True,text=True);assert r.returncode==0 and json.loads(r.stdout)==out
