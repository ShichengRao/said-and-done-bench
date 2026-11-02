import copy,itertools,random
from collections import deque
import pytest
from rollout import plan

def oracle(spec):
    ids=sorted(n['id'] for n in spec['nodes']); by={n['id']:n for n in spec['nodes']}
    initial=tuple(spec['initial'].get(i,'empty') for i in ids)
    def legal(s):
        occupied=[i for i,v in zip(ids,s) if v!='empty']
        return spec['min_ready']<=len(occupied)<=spec['max_total'] and len({by[i]['zone'] for i in occupied})>=spec['min_zones']
    if not legal(initial): raise ValueError
    # Build the entire legal-state graph independently, then breadth-first traversal.
    states=[s for s in itertools.product(('empty','old','new'),repeat=len(ids)) if legal(s)]
    states=set(states); q=deque([(initial,[])]); visited={initial}
    while q:
        s,path=q.popleft()
        if s.count('new')==spec['desired'] and s.count('old')==0 and all(s[ids.index(i)]=='empty' for i in ids if by[i]['maintenance']): return path
        neighbors=[]
        for index,i in enumerate(ids):
            if s[index]=='empty' and by[i]['eligible'] and not by[i]['maintenance']: op,v='start','new'
            elif s[index]!='empty': op,v='stop','empty'
            else: continue
            t=s[:index]+(v,)+s[index+1:]
            if t in states and t not in visited: neighbors.append((op,i,t))
        for op,i,t in sorted(neighbors):
            if t in visited: continue
            visited.add(t); q.append((t,path+[dict(op=op,node=i)]))
    return None

def cases():
    r=random.Random(735)
    for index in range(36):
        count=r.randint(4,7)
        nodes=[dict(id='node-'+str(i),zone='zone-'+str(i%3),eligible=r.random()>.17,maintenance=r.random()<.16) for i in range(count)]
        initial={n['id']:('new' if r.random()<.2 else 'old') for n in nodes[:3]}
        r.shuffle(nodes)
        yield dict(nodes=nodes,initial=initial,min_ready=r.choice([2,3]),max_total=r.choice([3,4]),min_zones=r.choice([1,2,3]),desired=3)

@pytest.mark.parametrize('spec',list(cases()))
def test_generated_state_spaces(spec):
    old=copy.deepcopy(spec)
    assert plan(spec)==oracle(spec)
    assert spec==old

def test_invalid_initial():
    with pytest.raises(ValueError): plan(dict(nodes=[],initial={},min_ready=1,max_total=2,min_zones=1,desired=1))

def test_already_done():
    spec=dict(nodes=[dict(id='x',zone='a',eligible=True,maintenance=False)],initial={'x':'new'},min_ready=1,max_total=1,min_zones=1,desired=1)
    assert plan(spec)==[]
