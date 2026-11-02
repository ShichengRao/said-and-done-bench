import copy,random

def cases(source):
    for seed in range(15):
        d=copy.deepcopy(source);rng=random.Random(seed)
        if seed%5==0:d['credentials'][2]['uses']=2
        if seed%5==1:d['handoffs'].append(dict(d['proposals'][0]['link']))
        if seed%5==2:d['credentials'][0]['until']=13
        if seed%5==3:d['credentials'][4]['capabilities']=[['dataset-q','read'],['other','erase']]
        if seed%5==4:d['request']['entry']=['c38']
        if seed%3==0:d['proposals'][0]['cost']=4
        rng.shuffle(d['credentials']);rng.shuffle(d['handoffs']);rng.shuffle(d['proposals'])
        yield 'route-'+str(seed),d
    for mode in ['cycle','missing']:
        d=copy.deepcopy(source);d['credentials'][0]['parent']='c14' if mode=='cycle' else 'absent'
        yield mode,d

def independent_checks(transform,source):
    result=transform(copy.deepcopy(source))
    assert all(row['credentials'] for row in result['candidates'])
    assert [len(row['states']) for row in result['frontiers']]==[1,1,2,1,0]
    assert result['owner_remedy']=={'proposals':['p12'],'cost':2,'path':['c14','c26','c57','c38','c49']}
    d=copy.deepcopy(source);d['handoffs'].append(dict(d['proposals'][0]['link']))
    assert transform(d)['ready']


def cli_success_cases():
    # Fresh schema-valid input, generated independently of the canonical task fixture.
    import random
    rng=random.Random(2907);tenant='cli-'+str(rng.randrange(10000));binding='binding-'+str(rng.randrange(10000));caps=[['data','read'],['data','erase']]
    credential=lambda name,cap:dict(id=name,parent=None,selectable=True,tenant=tenant,binding=binding,capabilities=[cap],uses=1,revoked_at=None,**{'from':0,'until':None})
    data=dict(request=dict(tenant=tenant,binding=binding,entry=['read-token'],steps=[dict(resource='data',operation='read',at=4),dict(resource='data',operation='erase',at=5)]),credentials=[credential('read-token',caps[0]),credential('erase-token',caps[1])],handoffs=[dict(source='read-token',target='erase-token',after=1,**{'from':3,'until':6})],proposals=[])
    return [('generated-cli',data)]
