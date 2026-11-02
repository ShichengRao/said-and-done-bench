import copy,random

def cases(source):
    for seed in range(16):
        d=copy.deepcopy(source);rng=random.Random(seed)
        for q in d['queries']:q['at']+=seed%7;q['terms']=['alpha'] if seed%2 else ['incident']
        if seed%3==0:d['membership'].append({'tenant':'t8','seq':9,'at':2,'member':'g:r2','group':'g:r1','op':'add'})
        if seed%4==0:d['documents'][2]['inherit']=False
        if seed%5==0:d['documents'][3]['deny']=['u:p7']
        rng.shuffle(d['documents']);rng.shuffle(d['membership']);rng.shuffle(d['queries'])
        yield 'visibility-'+str(seed),d
    d=copy.deepcopy(source);d['documents'].append(dict(d['documents'][-1],content={'text':'conflict'}))
    yield 'unqueried-tenant-conflict-is-irrelevant',d
    d=copy.deepcopy(source);d['documents'].append(dict(d['documents'][0],at=99,content={'text':'future'}))
    yield 'future-conflict-is-irrelevant',d
    for mode in ['revision','membership','cycle','missing']:
        d=copy.deepcopy(source)
        if mode=='revision':d['documents'].append(dict(d['documents'][0],content={'text':'conflict'}))
        if mode=='membership':d['membership'].append(dict(d['membership'][0],op='remove'))
        if mode=='cycle':d['documents'][0]['parent']='d2'
        if mode=='missing':d['documents'][1]['parent']='absent'
        yield mode,d

def independent_checks(transform,source):
    rows=transform(copy.deepcopy(source))['queries']
    assert rows[0]['visible']==['d1','d2','d3','d4']
    assert rows[1]['visible']==['d1','d2','d4'] and [x['document'] for x in rows[1]['hits']]==['d1','d4']
    assert rows[2]['visible']==['d4'] and rows[3]['visible']==[]
    assert rows[1]['hits'][1]['content']['attributes']=={'private_tag':'x8'}


def cli_success_cases():
    # Fresh schema-valid input, generated independently of the canonical task fixture.
    import random
    rng=random.Random(2903);tenant='cli-'+str(rng.randrange(10000));user='viewer-'+str(rng.randrange(10000))
    data=dict(queries=[dict(id='lookup',tenant=tenant,user=user,at=8,terms=['needle'])],documents=[dict(tenant=tenant,id='parent',seq=1,at=1,parent=None,deleted=False,inherit=False,allow=['g:readers'],deny=[],content={'text':'Root'}),dict(tenant=tenant,id='child',seq=2,at=2,parent='parent',deleted=False,inherit=True,allow=[],deny=[],content={'text':'A Needle!', 'opaque':{'n':rng.randrange(100)}})],membership=[dict(tenant=tenant,seq=1,at=1,member='u:'+user,group='g:inner',op='add'),dict(tenant=tenant,seq=2,at=2,member='g:inner',group='g:readers',op='add')])
    return [('generated-cli',data)]
