import copy,hashlib,json,random
import pytest
from recovery import restore

def digest(events):
    return hashlib.sha256(json.dumps(events,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def fixture(seed):
    r=random.Random(seed); initial={'a':100+seed,'b':80,'retired':9}; rows=initial.copy()
    b={'snapshot':{'sequence':7,'rows':initial},'segments':{'east':[],'west':[]},'commits':[]}
    counters={'east':30,'west':40}; expected={7:rows.copy()}
    for seq in range(8,14):
        tx='tx-'+str(seq); amount=r.randrange(1,10)
        ops=[('a',rows['a'],rows['a']-amount),('b',rows['b'],rows['b']+amount)]
        if seq==10: ops.append(('retired',9,None))
        if seq==12: ops.append(('new',None,seed+3))
        parts={}
        for ordinal,(key,before,after) in enumerate(ops):
            shard=r.choice(['east','west']); counters[shard]+=1
            event=dict(lsn=counters[shard],tx=tx,ordinal=ordinal,key=key,before=before,after=after)
            parts.setdefault(shard,[]).append(event); b['segments'][shard].append(event)
            if after is None: rows.pop(key,None)
            else: rows[key]=after
        proofs={s:dict(first=es[0]['lsn'],last=es[-1]['lsn'],sha256=digest(es)) for s,es in parts.items()}
        b['commits'].append(dict(sequence=seq,tx=tx,parts=proofs)); expected[seq]=rows.copy()
    for es in b['segments'].values():
        es.extend(copy.deepcopy(es[:2])); r.shuffle(es)
    b['segments']['east'].append(dict(lsn=999,tx='uncommitted',ordinal=0,key='a',before=rows['a'],after=0))
    r.shuffle(b['commits'])
    return b,expected

@pytest.mark.parametrize('seed',range(14))
def test_recovery_targets_and_input_purity(seed):
    b,states=fixture(seed); original=copy.deepcopy(b)
    for target,state in states.items():
        assert restore(b,target)=={'sequence':target,'rows':state,'transactions':['tx-'+str(s) for s in range(8,target+1)]}
    assert b==original

@pytest.mark.parametrize('kind',['missing_seal','missing_event','conflict','digest','precondition','ordinal'])
def test_invalid_evidence_rejected(kind):
    b,_=fixture(19)
    if kind=='missing_seal': b['commits']=[s for s in b['commits'] if s['sequence']!=9]
    elif kind=='missing_event':
        for s in b['segments']: b['segments'][s]=[e for e in b['segments'][s] if not(e['tx']=='tx-8' and e['ordinal']==0)]
    elif kind=='conflict':
        s=next(s for s,v in b['segments'].items() if v); e=copy.deepcopy(b['segments'][s][0]); e['after']=777; b['segments'][s].append(e)
    else:
        seal=next(s for s in b['commits'] if s['sequence']==8)
        shard=next(iter(seal['parts']))
        events={e['lsn']:e for e in b['segments'][shard] if e['tx']=='tx-8'}
        for e in b['segments'][shard]:
            if e['tx']=='tx-8':
                if kind=='digest': seal['parts'][shard]['sha256']='0'*64
                elif kind=='precondition': e['before']=888
                else: e['ordinal']=99
        if kind!='digest': seal['parts'][shard]['sha256']=digest([events[k] for k in sorted(events)])
    with pytest.raises(ValueError): restore(b,13)
