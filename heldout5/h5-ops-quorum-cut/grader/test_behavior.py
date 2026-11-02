import copy,hashlib,itertools,json,random
from collections import deque
from pathlib import Path
import pytest
from evacuation import assess

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'))
def oracle(s):
    reps={r['id']:r for r in s['replicas']};ids=sorted(reps);nodes={n['id']:n for n in s['nodes']}
    start=tuple((r,'active',reps[r]['initial']['node'],reps[r]['initial']['image']) for r in ids)
    def valid(copies):
        resources={n:[0,0] for n in nodes};racks=set();ready={k:set() for k in s['policy']};zones={k:set() for k in ready}
        for rid,kind,n,image in copies:
            replica=reps[rid];service=replica['service'];resources[n][0]+=replica['cpu'];resources[n][1]+=replica['memory'];pair=(service,nodes[n]['rack'])
            if pair in racks:return False
            racks.add(pair)
            if kind=='active' or image=='ready':ready[service].add(rid);zones[service].add(nodes[n]['zone'])
        return all(resources[n][0]<=node['cpu'] and resources[n][1]<=node['memory'] for n,node in nodes.items()) and all(len(ready[k])>=v['min_ready'] and len(zones[k])>=v['min_zones'] for k,v in s['policy'].items())
    def goal(c):return len(c)==len(ids) and all(kind=='active' and image=='new' and nodes[n]['rack']!=s['maintenance_rack'] and nodes[n]['zone'] in reps[r]['zones'] for r,kind,n,image in c)
    queue=deque([start]);paths={start:[]};solution=None
    while queue:
        c=queue.popleft()
        if goal(c) and solution is None:solution=paths[c]
        active={r:(r,k,n,image) for r,k,n,image in c if k=='active'};shadow=next((x for x in c if x[1]=='shadow'),None);nexts=[]
        for rid in ids:
            if rid in active and (shadow is None or shadow[0]!=rid):nexts.append((('stop',rid,active[rid][2]),tuple(x for x in c if x!=active[rid])))
            if shadow is None:
                for n,node in nodes.items():
                    if node['rack']!=s['maintenance_rack'] and node['zone'] in reps[rid]['zones'] and (rid not in active or active[rid][2]!=n):nexts.append((('start',rid,n),c+((rid,'shadow',n,'pending'),)))
        if shadow:
            rid,_,n,phase=shadow
            if phase=='pending':nexts.append((('ready',rid,n),tuple(x for x in c if x!=shadow)+((rid,'shadow',n,'ready'),)))
            else:nexts.append((('commit',rid,n),tuple(x for x in c if x[0]!=rid)+((rid,'active',n,'new'),)))
        for action,raw in sorted(nexts):
            nxt=tuple(sorted(raw))
            if nxt not in paths and valid(nxt):paths[nxt]=paths[c]+[dict(zip(('op','replica','node'),action))];queue.append(nxt)
    encoded=[]
    for c in paths:
        a={r:(n,image) for r,kind,n,image in c if kind=='active'};sh=next(([r,n,image=='ready'] for r,kind,n,image in c if kind=='shadow'),None)
        encoded.append(canonical(dict(active=[[r,*a.get(r,(None,None))] for r in ids],shadow=sh)))
    digest=hashlib.sha256(canonical(sorted(encoded)).encode()).hexdigest();static=None
    dest={r:sorted(n for n,v in nodes.items() if v['rack']!=s['maintenance_rack'] and v['zone'] in reps[r]['zones']) for r in ids}
    for placement in itertools.product(*(dest[r] for r in ids)):
        copies=tuple((r,'active',n,'new') for r,n in zip(ids,placement))
        if valid(copies):static=[[r,n] for r,n in zip(ids,placement)];break
    return static,len(paths),digest,solution

def expect(s):
    static,count,sha,plan=oracle(s);requests=sorted(s['requests'],key=lambda q:q['id']);candidates=[]
    for bits in itertools.product((0,1),repeat=len(requests)):
        qs=[q for q,b in zip(requests,bits) if b];changed=copy.deepcopy(s);nodes={n['id']:n for n in changed['nodes']}
        for q in qs:nodes[q['node']]['cpu']+=q['delta_cpu'];nodes[q['node']]['memory']+=q['delta_memory']
        found=plan if not qs else oracle(changed)[3]
        if found is not None:candidates.append((sum(q['cost'] for q in qs),len(qs),[q['id'] for q in qs],found))
    chosen=min(candidates,key=lambda x:x[:3]) if candidates else None;remedy=dict(requests=chosen[2],cost=chosen[0],plan=chosen[3]) if chosen else None
    return dict(static_placement=static,reachable_count=count,reachable_sha256=sha,plan=plan,remedy=remedy,blocker=None if plan is not None else dict(kind='transition_unreachable',reachable_count=count,reachable_sha256=sha,owner_requests=remedy['requests'] if remedy else []))

@pytest.mark.parametrize('seed',range(8))
def test_small_state_spaces_and_counterfactuals(seed):
    rng=random.Random(seed)
    s=dict(nodes=[dict(id='n'+str(i),rack='r'+str(i),zone='z'+str(i%2),cpu=2,memory=rng.choice([1,2])) for i in range(4)],replicas=[dict(id='p0',service='a',cpu=1,memory=1,zones=['z0'],initial=dict(node='n0',image='old')),dict(id='p1',service='b',cpu=1,memory=1,zones=['z1'],initial=dict(node='n1',image='old'))],policy={'a':dict(min_ready=seed%2,min_zones=seed%2),'b':dict(min_ready=1,min_zones=1)},maintenance_rack='r0' if seed%3==0 else 'none',requests=[dict(id='q',node='n2',delta_cpu=0,delta_memory=1,cost=2)])
    old=copy.deepcopy(s);assert assess(s)==expect(s) and s==old

def test_canonical_unreachable_and_joint_owner_change():
    s=json.loads(Path('data/input.json').read_text());out=assess(s)
    assert out==expect(s)==json.loads(Path('/grader/expected_report.json').read_text())
    assert out['static_placement'] and out['plan'] is None
    assert len(out['remedy']['requests'])==2

def test_order_independence_and_no_proposals():
    s=json.loads(Path('data/input.json').read_text());s['nodes'].reverse();s['replicas'].reverse();s['requests']=[]
    assert assess(s)==expect(s) and assess(s)['remedy'] is None

def test_ready_shadow_reservation_and_already_done():
    s=dict(nodes=[dict(id='a',rack='r1',zone='z',cpu=1,memory=1),dict(id='b',rack='r2',zone='z',cpu=0,memory=1)],replicas=[dict(id='p',service='svc',cpu=1,memory=1,zones=['z'],initial=dict(node='a',image='old'))],policy={'svc':dict(min_ready=1,min_zones=1)},maintenance_rack='none',requests=[])
    assert assess(s)==expect(s) and assess(s)['plan'] is None
    s['replicas'][0]['initial']['image']='new';assert assess(s)==expect(s) and assess(s)['plan']==[]


def test_cli_json_contract(tmp_path):
    import subprocess,sys
    s=json.loads(Path('data/input.json').read_text())
    for i in range(2):
        if i:s['requests']=[]
        source=tmp_path/('case-'+str(i)+'.json');source.write_text(json.dumps(s))
        run=subprocess.run([sys.executable,'evacuation.py',str(source)],capture_output=True,text=True,timeout=40)
        assert run.returncode==0,run.stderr
        assert json.loads(run.stdout)==expect(s)
