import copy,random

def cases(source):
    for seed in range(16):
        d=copy.deepcopy(source);rng=random.Random(seed)
        if seed%4==0:d['request']['separate'].pop(seed%5)
        if seed%4==1:d['request']['at']=75
        if seed%4==2:d['owners'][0]['capacity']=3
        if seed%4==3:d['proposals'][0]['cost']=5
        if seed%5==0:d['request']['groups'][2]['units']=2
        rng.shuffle(d['authority']);rng.shuffle(d['request']['groups']);rng.shuffle(d['owners']);rng.shuffle(d['proposals'])
        yield 'assignment-'+str(seed),d
    d=copy.deepcopy(source);d['authority'].append(dict(d['authority'][0],scope='s9'))
    yield 'authority-conflict',d
    d=copy.deepcopy(source);d['owners'][0]['capacity']=0
    yield 'overreserved',d

def independent_checks(transform,source):
    got=transform(copy.deepcopy(source))
    assert all(value==['u14','u27'] for value in got['candidates'].values())
    assert got['infeasible_core']==['g1','g2','g3','g4','g5']
    assert got['owner_remedy']=={'proposals':['p14'],'cost':2,'assignment':{'g1':'u14','g2':'u27','g3':'u38','g4':'u14','g5':'u27'}}
    for index in range(5):
        d=copy.deepcopy(source);d['request']['separate'].pop(index)
        assert transform(d)['ready']


def cli_success_cases():
    # Fresh schema-valid input, generated independently of the canonical task fixture.
    import random
    rng=random.Random(2905);owner='owner-'+str(rng.randrange(10000));group='group-'+str(rng.randrange(10000));scope='scope-z'
    data=dict(request=dict(at=10,groups=[dict(id=group,units=2,scopes=[scope])],separate=[]),owners=[dict(id=owner,capacity=4,**{'from':0,'until':None})],reservations=[dict(owner=owner,units=1,**{'from':5,'until':12})],authority=[dict(seq=3,at=2,owner=owner,scope=scope,op='grant',until=15)],proposals=[])
    return [('generated-cli',data)]
