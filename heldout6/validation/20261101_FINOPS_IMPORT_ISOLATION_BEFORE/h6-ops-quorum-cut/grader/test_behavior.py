import copy,itertools,json,subprocess,sys
from pathlib import Path
import pytest
import planner as p
from oracle import audit as expected,authority,full_search
from cases import alternate_cases,approved

def production():return json.loads((Path(__file__).parent/'original/data/input.json').read_text())

def test_canonical_full_transition_oracle():
 d=production();out=p.audit(d);assert out==expected(d)
 assert out['static_final_valid'] and not out['certifiable']
 assert (out['reachable_count'],out['stable_count'])==(1473,269)
 assert out['owner_plan']['cost']==3 and out['owner_plan']['requests']==['approve-relay-03']
 assert len(out['owner_plan']['plan'])==45

def test_supplied_interacting_obstacle_and_feasible_relaxations():
 d=production();edges=authority(d);result,states=full_search(d,edges,True);us=sorted(d['units'])
 stable=[(pos,im) for pos,im,sh in states if sh is None]
 assert all(any(all(pos[i]==d['target'][us[i]] and im[i]=='new' for i in ix) for pos,im in stable) for ix in itertools.combinations(range(5),3))
 for mutate in ('small','zone','rack'):
  a=copy.deepcopy(d)
  if mutate=='small':
   for u in a['units']:a['units'][u]['size']=1
  elif mutate=='zone':
   for g in a['groups']:a['groups'][g]['min_zones']=1
  else:a['rack_capacity']['r2']=6
  out=p.audit(a);assert out==expected(a) and out['certifiable']
  assert len(out['plan'])==(45 if mutate=='zone' else 99)

def test_actual_owner_edges_and_minimum_request():
 base=production()
 for ids,reachable in [({'approve-relay-03'},True),({'direct-heavy-15'},False),({'east-return-52'},False),({'direct-heavy-15','east-return-52'},False),({'cross-rack-30'},True),({'direct-transfer-24'},True)]:
  d=approved(base,ids);out=p.audit(d);assert out==expected(d) and out['certifiable']==reachable
  if reachable:assert out['blocker'] is None and out['owner_plan']['requests']==[] and out['owner_plan']['cost']==0

def test_capacity_counts_shadow_and_keeps_uncommittable_receipts():
 d=production();result,states=full_search(d,authority(d),True)
 # Copy/ready records whose resulting active voter zones are invalid remain reachable.
 dead=0
 for pos,im,sh in states:
  if sh is None or sh[2]!='ready':continue
  units=sorted(d['units']);i=units.index(sh[0]);nextpos=list(pos);nextpos[i]=sh[1]
  if any(len({d['nodes'][nextpos[j]]['zone'] for j,u in enumerate(units) if d['units'][u]['group']==g})<r['min_zones'] for g,r in d['groups'].items()):dead+=1
 assert dead==91 and p.audit(d)['reachable_count']==result['reachable_count']
 # A valid saturated rack never gains space by counting only active copies.
 d={'at':1,'nodes':{'a':dict(rack='r',zone='x',capacity=3),'b':dict(rack='r',zone='y',capacity=3)},'rack_capacity':{'r':3},'units':{'u':dict(group='g',size=3,allowed_final=['b'])},'groups':{'g':dict(quorum=1,min_zones=1)},'initial':{'positions':{'u':'a'},'images':{'u':'old'}},'target':{'u':'b'},'links':[dict(id='l',revision=1,source='a',target='b',enabled=True,valid_from=0,valid_to=2)],'owner_requests':[]}
 assert p.audit(d)==expected(d) and p.audit(d)['reachable_count']==1

def test_revision_expiry_direction_and_conflicts():
 d=production();out=p.audit(d);assert ('n0','n2') in authority(d) and ('n0','n3') not in authority(d)
 d['links'].reverse();assert p.audit(d)==out
 d=production();d['links']=[r for r in d['links'] if not(r['id']=='regional-relay' and r['revision']==2)]
 assert p.audit(d)==expected(d) and p.audit(d)['certifiable']
 d=production();r=copy.deepcopy(d['links'][0]);d['links'].append({**r,'enabled':not r['enabled']})
 with pytest.raises(ValueError):p.audit(d)
 # Even superseded conflicting deliveries are evidence errors.
 d=production();r=next(r for r in d['links'] if r['id']=='regional-relay' and r['revision']==1);d['links'].append({**r,'enabled':False})
 with pytest.raises(ValueError):p.audit(d)

def test_generated_and_metamorphic_models_against_full_oracle():
 for name,d in alternate_cases(production()):assert p.audit(d)==expected(d),name

def test_final_policy_is_not_a_staging_rule():
 d=approved(production(),{'approve-relay-03'});out=p.audit(d);assert out==expected(d) and out['certifiable']
 assert any(a=='start' and n not in d['units'][u]['allowed_final'] for a,u,n in out['plan'])
 for u in d['units']:d['units'][u]['allowed_final']=[d['target'][u]]
 assert p.audit(d)==expected(d) and p.audit(d)['certifiable']
 d['units']['u0']['allowed_final']=[];out=p.audit(d);assert out==expected(d) and not out['certifiable'] and out['plan'] is None and out['owner_plan'] is None

def test_input_preservation_and_alternate_cli(tmp_path):
 d=approved(production(),{'cross-rack-30'});old=copy.deepcopy(d);out=p.audit(d);assert d==old
 f=tmp_path/'alternate.json';f.write_text(json.dumps(d));r=subprocess.run([sys.executable,p.__file__,str(f)],capture_output=True,text=True)
 assert r.returncode==0 and json.loads(r.stdout)==out
