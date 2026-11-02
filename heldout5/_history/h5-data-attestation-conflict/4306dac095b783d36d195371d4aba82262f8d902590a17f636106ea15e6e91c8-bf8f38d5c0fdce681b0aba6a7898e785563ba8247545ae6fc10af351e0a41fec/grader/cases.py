import copy,hashlib,json,random

def reseal(d):
    unique={row['seq']:row for row in d['receipts']};previous='0'*64
    for seq,row in sorted(unique.items()):
        row['previous']=previous;payload={k:v for k,v in row.items() if k!='digest'}
        row['digest']=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest();previous=row['digest']
    d['receipts']=list(unique.values());d['manifest']={'count':len(unique),'root':previous}

def cases(source):
    for seed in range(14):
        d=copy.deepcopy(source);rng=random.Random(seed)
        if seed%4==0:d['memberships'][1]['until']=35
        if seed%4==1:d['artifacts'][0]['created']=21
        if seed%4==2:d['receipts'][2]['ack']=False
        if seed%4==3:d['requests'][1]['replay_at']=24
        if seed%5==0:d['ownership'][0]['tenant']='t4'
        reseal(d)
        for key in ['receipts','artifacts','ownership','memberships','attempts']:rng.shuffle(d[key])
        yield 'audit-'+str(seed),d
    for mode in ['tampered','missing','cycle','ownership','noncausal','membership']:
        d=copy.deepcopy(source)
        if mode=='tampered':d['receipts'][2]['ack']=False
        if mode=='missing':d['receipts']=[r for r in d['receipts'] if r['seq']!=3]
        if mode=='cycle':d['artifacts'][0]['parents']=['b33']
        if mode=='ownership':d['ownership'].append(dict(d['ownership'][0],tenant='t9'))
        if mode=='noncausal':d['artifacts'][0]['created']=27
        if mode=='membership':d['memberships'].append(dict(d['memberships'][0],group='different'))
        yield mode,d

def independent_checks(transform,source):
    result=transform(copy.deepcopy(source))
    assert result['violations']==[3]
    assert result['receipt_checks'][1]['unauthorized']==[['b11','o9','t8']]
    assert result['safe_replays']==[{'receipt':3,'at':50,'artifact':'b44'}]
    assert result['receipt_checks'][2]['unauthorized']==[]
    d=copy.deepcopy(source);d['memberships'][1]['until']=35
    assert transform(d)['certifiable']


def cli_success_cases():
    # Fresh schema-valid input, generated independently of the canonical task fixture.
    import random
    rng=random.Random(2908);tenant='cli-'+str(rng.randrange(10000));principal='principal-'+str(rng.randrange(10000));logical='logical-z'
    receipt=dict(seq=1,attempt='attempt-z',at=8,ack=True,previous='0'*64)
    receipt['digest']=hashlib.sha256(json.dumps(receipt,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    data=dict(manifest=dict(count=1,root=receipt['digest']),receipts=[receipt],attempts=[dict(id='attempt-z',request='request-z',artifact='copy-z')],requests=[dict(id='request-z',principal=principal,replay_at=9)],artifacts=[dict(id='copy-z',created=4,logical=[logical],parents=[])],ownership=[dict(logical=logical,tenant=tenant,**{'from':0,'until':None})],memberships=[dict(principal=principal,seq=1,at=1,group='auditors',op='grant',until=10)],policy=[dict(group='auditors',tenant=tenant)],replacements=[])
    return [('generated-cli',data)]
