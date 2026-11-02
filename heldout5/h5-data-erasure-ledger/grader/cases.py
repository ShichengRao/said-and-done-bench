import copy,random

def cases(source):
    for seed in range(14):
        d=copy.deepcopy(source);r=random.Random(seed)
        d['catalog']['at']=35+seed
        d['catalog']['cutover']=20+seed
        d['requests'][0]['through']=8+seed*2
        if seed%3==0:d['requests'].append({'id':'q9','tenant':'t52','subject':'s1','through':99})
        if seed%4==0:d['holds'].append({'id':'h9','version':'v13','from':0,'until':None})
        if seed%5==0:d['identity'].append(dict(d['identity'][0]))
        for row in d['catalog']['versions']:row['arbitrary']={'seed':seed}
        r.shuffle(d['changes']);r.shuffle(d['catalog']['versions']);r.shuffle(d['identity'])
        yield 'lineage-'+str(seed),d
    for mode in ['cycle','missing','identity','sequence','version']:
        d=copy.deepcopy(source)
        if mode=='cycle':d['catalog']['versions'][0]['parents']=['v13']
        if mode=='missing':d['catalog']['versions'][1]['parents']=['absent']
        if mode=='identity':d['identity'].append(dict(d['identity'][0],subject='s9'))
        if mode=='sequence':d['changes'].append(dict(d['changes'][0],op='delete'))
        if mode=='version':d['catalog']['versions'].append(dict(d['catalog']['versions'][0],payload={}))
        yield mode,d

def independent_checks(transform,source):
    result=transform(copy.deepcopy(source))
    assert [v['version'] for v in result['survivors']]==['v21','v14','v15']
    assert result['purge_versions']==['v13','v22']
    assert [v['version'] for v in result['retained_for_hold']]==['v11','v12']
    assert [v['object'] for v in result['suppressed']]==['o3','o6']
    assert result['survivors'][0]['payload']['nested']=={'x':2}


def cli_success_cases():
    # Fresh schema-valid input, generated independently of the canonical task fixture.
    import random
    rng=random.Random(2902);tenant='cli-'+str(rng.randrange(10000));subject='subject-'+str(rng.randrange(10000));alias='historic'
    version=dict(version='source-v1',object='source',parents=[],identities=[dict(tenant=tenant,alias=alias,at=4)],payload={'private':'retain exactly'})
    derived=dict(version='derived-v2',object='view',parents=['source-v1'],identities=[],metadata={'seed':rng.randrange(99)})
    data=dict(catalog=dict(watermark=1,cutover=3,at=10,versions=[version],heads={'source':'source-v1'}),changes=[dict(seq=3,object='view',op='put',value=derived)],identity=[dict(tenant=tenant,alias=alias,subject=subject,**{'from':0,'until':None})],requests=[dict(id='erase',tenant=tenant,subject=subject,through=5)],holds=[dict(id='hold',version='source-v1',**{'from':0,'until':20})])
    return [('generated-cli',data)]
