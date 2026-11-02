import copy,random

def cases(source):
    for seed in range(14):
        d=copy.deepcopy(source);rng=random.Random(seed)
        for node in d['topology']:node['capacity']+=rng.randrange(4)
        if seed%3==0:d['catalog']['datasets'][0]['key']='k9'
        if seed%3==1:d['topology'][1]['domain']='z3'
        if seed%4==0:d['catalog']['at']=70
        if seed%4==1:d['catalog']['datasets'][1]['chunks'][2]['bytes']=1
        if seed%5==0:d['catalog']['datasets'].pop()
        rng.shuffle(d['topology']);rng.shuffle(d['reservations']);rng.shuffle(d['catalog']['datasets'])
        for row in d['catalog']['datasets']:rng.shuffle(row['chunks'])
        yield 'allocation-'+str(seed),d
    d=copy.deepcopy(source);d['topology'][0]['capacity']+=1;d['topology'][2]['capacity']+=2
    yield 'minimum-remedy-applied',d
    for mode in ['reservation','chunk','overreserved','unknown']:
        d=copy.deepcopy(source)
        if mode=='reservation':d['reservations'].append(dict(d['reservations'][0],bytes=1))
        if mode=='chunk':d['catalog']['datasets'][0]['chunks'].append(dict(d['catalog']['datasets'][0]['chunks'][0],bytes=99))
        if mode=='overreserved':d['topology'][0]['capacity']=0
        if mode=='unknown':d['reservations'][0]['node']='absent'
        yield mode,d

def independent_checks(transform,source):
    got=transform(copy.deepcopy(source))
    assert got['dataset_bytes']=={'d17':4,'d27':4,'d37':4}
    assert got['available_bytes']=={'n14':7,'n26':5,'n31':6,'n48':6}
    assert got['infeasible_core']==['d17','d27','d37'] and got['capacity_remedy']['total_bytes']==3
    assert got['capacity_remedy']['extra_bytes']=={'n14':1,'n31':2}
    for removed in range(3):
        d=copy.deepcopy(source);d['catalog']['datasets'].pop(removed)
        assert transform(d)['ready'] is True
    d=copy.deepcopy(source)
    for node in d['topology']:node['capacity']+=got['capacity_remedy']['extra_bytes'].get(node['id'],0)
    assert transform(d)['ready'] is True


def cli_success_cases():
    # Fresh schema-valid input, generated independently of the canonical task fixture.
    import random
    rng=random.Random(2906);dataset='dataset-'+str(rng.randrange(10000));size=rng.randrange(2,6);node_ids=['cli-node-a','cli-node-b']
    data=dict(catalog=dict(at=10,datasets=[dict(id=dataset,barrier=5,regions=['zone'],key='key-z',replicas=2,chunks=[dict(id='chunk',seq=2,op='put',bytes=size),dict(id='chunk',seq=9,op='put',bytes=100)])]),topology=[dict(id=n,domain='domain-'+str(i),region='zone',capacity=size+1,keys=['key-z'],cdc=True) for i,n in enumerate(node_ids)],reservations=[dict(id='reservation',node=node_ids[0],bytes=1,**{'from':0,'until':None})])
    return [('generated-cli',data)]
