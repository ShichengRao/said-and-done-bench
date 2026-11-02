import copy,random

def cases(source):
    for seed in range(12):
        d=copy.deepcopy(source);rng=random.Random(seed)
        # Independent state/value/time perturbations, extra transactions, not just identifier renaming.
        for c in d['snapshot']['customers']: c['seats']+=seed+10;c['opaque']={'n':seed}
        d['snapshot']['as_of']=30+(seed%2)
        for row in d['deliveries']:
            if row['op']=='seats_delta' and row['tx']=='t4': row['value']+=seed
        if seed%3==0: d['identity'].append(dict(d['identity'][0]))
        if seed%4==0: d['decisions'].append(dict(d['decisions'][0]))
        for value in d.values():
            if isinstance(value,list):rng.shuffle(value)
        yield 'replay-'+str(seed),d
    for mode in ['missing','conflict','identity','negative','order','type','decision']:
        d=copy.deepcopy(source)
        if mode=='missing': d['deliveries']=[r for r in d['deliveries'] if r['stream']!='s2']
        if mode=='conflict': d['deliveries'].append(dict(d['deliveries'][0],value='conflicting'))
        if mode=='identity': d['identity'].append(dict(d['identity'][0],customer='c29'))
        if mode=='negative':
            for r in d['deliveries']:
                if r['stream']=='s2':r['value']=0
        if mode=='order': d['deliveries'][0]['order']=9
        if mode=='type': d['deliveries'][0]['value']=42
        if mode=='decision':d['decisions'].append(dict(d['decisions'][0],decision='abort'))
        yield mode,d
    d=copy.deepcopy(source);d['snapshot']['watermarks']['r17']=20
    d['identity']=[];d['decisions']=[r for r in d['decisions'] if r['tenant']=='r17']
    yield 'covered-payload-not-revalidated',d


    # Identity conflicts are invalid even if payload is outside selected commits.
    for tx in ['t6','t8','t1']:
        d=copy.deepcopy(source)
        if tx=='t1':
            row=dict(d['deliveries'][0],tx='t1',stream='s9',offset=1)
            d['deliveries'].append(row)
        else:row=next(r for r in d['deliveries'] if r['tx']==tx)
        d['deliveries'].append(dict(row,value='conflicting duplicate'))
        yield 'out-of-window-delivery-conflict-'+tx,d
    for tx in ['t6','t8','t1']:
        d=copy.deepcopy(source)
        if tx=='t1':
            row=dict(d['deliveries'][0],tx='t1',stream='s9',offset=1)
            d['deliveries'].append(row)
        else:row=next(r for r in d['deliveries'] if r['tx']==tx)
        row['alias']='unresolvable';row['op']='unsupported';row['value']={'invalid':'payload'}
        yield 'unselected-payload-ignored-'+tx,d

def independent_checks(transform,source):
    got=transform(copy.deepcopy(source))
    assert [(c['tenant'],c['id'],c['seats'],c['tier'],c['active']) for c in got['customers']]==[('r17','c11',7,'base',True),('r17','c29',2,'team',True),('r23','c11',6,'base',True)]
    assert got['watermarks']=={'r17':24,'r23':20} and got['delivery_duplicates']==1
    assert got['applied'][0]['targets']==['c11','c11','c29']


def cli_success_cases():
    # Fresh schema-valid input, generated independently of the canonical task fixture.
    import random
    rng=random.Random(2901);tenant='cli-'+str(rng.randrange(10000));customer='subject-'+str(rng.randrange(10000));alias='legacy-'+str(rng.randrange(10000));count=rng.randrange(4,20)
    row=dict(tenant=tenant,tx='transaction-z',stream='feed-q',offset=8,order=0,at=5,alias=alias,op='seats_delta',value=3)
    data=dict(snapshot=dict(as_of=8,watermarks={tenant:2},customers=[dict(tenant=tenant,id=customer,seats=count,tier='standard',active=True,opaque={'keep':[1,'x']})]),decisions=[dict(tenant=tenant,tx='transaction-z',seq=7,decision='commit',members=[['feed-q',8]])],deliveries=[row,dict(row)],identity=[dict(tenant=tenant,alias=alias,customer=customer,**{'from':0,'until':None})])
    return [('generated-cli',data)]
