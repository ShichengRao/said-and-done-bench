import copy,random

def cases(source):
    for seed in range(16):
        d=copy.deepcopy(source);rng=random.Random(seed)
        d['request']['k']=1+seed%4
        if seed%3==0:d['request']['as_of']=35
        if seed%4==0:d['consent'][0]['allow']=False
        if seed%5==0:d['crm'][3]['segment']='a'
        if seed%6==0:d['tickets'].append(dict(d['tickets'][0],id='new-ticket'))
        for key in ['tickets','bridge','crm','consent']:rng.shuffle(d[key])
        yield 'export-'+str(seed),d
    for mode in ['bridge','ticket','crm','missing','consent']:
        d=copy.deepcopy(source)
        if mode=='bridge':d['bridge'].append(dict(d['bridge'][0],target=['crm','c9']))
        if mode=='ticket':d['tickets'].append(dict(d['tickets'][-1],status='closed'))
        if mode=='crm':d['crm'].append(dict(d['crm'][0],segment='other'))
        if mode=='missing':d['crm']=[row for row in d['crm'] if row['customer']!='c1']
        if mode=='consent':d['consent'].append(dict(d['consent'][0],allow=False))
        yield mode,d
    d=copy.deepcopy(source);d['bridge'].append(dict(d['bridge'][0],purpose='marketing',target=['crm','different']))
    yield 'unrelated-purpose-not-authority',d


    d=copy.deepcopy(source)
    d['consent'][0]['allow']=False
    # A denied historical event never requires a later-time consent lookup.
    d['consent'].extend([dict(d['consent'][0],seq=3,at=40,allow=True),dict(d['consent'][0],seq=3,at=40,allow=False)])
    yield 'denied-event-does-not-read-now-state',d

def independent_checks(transform,source):
    result=transform(copy.deepcopy(source))
    assert [(r['region'],r['segment'],r['members'],r['tickets'],r['suppression']) for r in result['cohorts']]==[('north','a',3,3,None),('north','b',None,None,'small_group'),('north','c',None,None,'complementary'),('south','d',2,3,None)]
    assert result['regions']==[{'tenant':'t6','region':'north','members':6,'tickets':6},{'tenant':'t6','region':'south','members':2,'tickets':3}]
    assert result['excluded']=={'deleted':1,'status':1,'consent_at_event':0,'consent_now':1}


def cli_success_cases():
    # Fresh schema-valid input, generated independently of the canonical task fixture.
    import random
    rng=random.Random(2904);tenant='cli-'+str(rng.randrange(10000));customer='customer-'+str(rng.randrange(10000));purpose='support-audit'
    data=dict(request=dict(tenants=[tenant],purpose=purpose,as_of=20,statuses=['closed'],k=1),tickets=[dict(tenant=tenant,id='ticket-z',revision=2,recorded=8,at=5,external='ticket-account',status='closed',deleted=False,email='never-output@example.test')],bridge=[dict(tenant=tenant,source=['support','ticket-account'],target=['relay','middle'],purpose=purpose,**{'from':0,'until':None}),dict(tenant=tenant,source=['relay','middle'],target=['crm',customer],purpose=purpose,**{'from':0,'until':None})],consent=[dict(tenant=tenant,customer=customer,seq=1,at=0,purpose=purpose,allow=True)],crm=[dict(tenant=tenant,customer=customer,seq=1,at=0,region='region-'+str(rng.randrange(20)),segment='cohort',email='private@example.test')])
    return [('generated-cli',data)]
