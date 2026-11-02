import copy,json
from pathlib import Path
from evacuation import assess

def test_full_resource_and_topology_certificate():
    spec=json.loads(Path('data/input.json').read_text()); original=copy.deepcopy(spec)
    expected=json.loads((Path('/grader')/'expected_report.json').read_text())
    assert assess(spec)==expected
    assert spec==original

def test_no_spurious_block_with_extra_capacity():
    spec=json.loads(Path('data/input.json').read_text())
    spec['nodes'].extend([dict(id='added-east',rack='new-east',zone='east',cpu=8,memory=16),dict(id='added-west',rack='new-west',zone='west',cpu=8,memory=16)])
    out=assess(spec)
    assert out['feasible'] and out['maximum_placed']==6 and out['unplaced']==[]

def test_same_service_cannot_share_rack():
    spec={'maintenance_rack':'off','nodes':[dict(id='a',rack='one',zone='x',cpu=8,memory=8),dict(id='b',rack='one',zone='x',cpu=8,memory=8)],'pods':[dict(id='a',service='db',zones=['x'],cpu=1,memory=1),dict(id='b',service='db',zones=['x'],cpu=1,memory=1)]}
    assert assess(spec)=={'feasible':False,'required':2,'maximum_placed':1,'placement':{'a':'a'},'unplaced':['b'],'maintenance_rack':'off'}


def test_generated_resource_and_affinity_variants():
    import itertools, random
    rng=random.Random(551)
    for case in range(18):
        nodes=[dict(id='n'+str(i),rack='r'+str(i//2),zone='z'+str(i%2),cpu=rng.randint(2,6),memory=rng.randint(3,8)) for i in range(4)]
        pods=[dict(id='p'+str(i),service='s'+str(i%2),zones=rng.choice([['z0'],['z1'],['z0','z1']]),cpu=rng.randint(1,3),memory=rng.randint(1,5)) for i in range(5)]
        spec=dict(nodes=nodes,pods=pods,maintenance_rack=rng.choice(['off','r0']))
        choices=[None]+[n['id'] for n in nodes if n['rack']!=spec['maintenance_rack']]
        by={n['id']:n for n in nodes}; legal=[]
        for assignment in itertools.product(choices,repeat=len(pods)):
            assigned=[(p,n) for p,n in zip(pods,assignment) if n is not None]
            if any(by[n]['zone'] not in p['zones'] for p,n in assigned):continue
            if len({(p['service'],by[n]['rack']) for p,n in assigned})!=len(assigned):continue
            if any(sum(p['cpu'] for p,n in assigned if n==i)>node['cpu'] or sum(p['memory'] for p,n in assigned if n==i)>node['memory'] for i,node in by.items()):continue
            legal.append(sorted((p['id'],n) for p,n in assigned))
        best=min(legal,key=lambda pairs:(-len(pairs),pairs))
        expected=dict(feasible=len(best)==len(pods),required=len(pods),maximum_placed=len(best),placement=dict(best),unplaced=sorted(p['id'] for p in pods if p['id'] not in dict(best)),maintenance_rack=spec['maintenance_rack'])
        rng.shuffle(spec['nodes']);rng.shuffle(spec['pods'])
        assert assess(spec)==expected
