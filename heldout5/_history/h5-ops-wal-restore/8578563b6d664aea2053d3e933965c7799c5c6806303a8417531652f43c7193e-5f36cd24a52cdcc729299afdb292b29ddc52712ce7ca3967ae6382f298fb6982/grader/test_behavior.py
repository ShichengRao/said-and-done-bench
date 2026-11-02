import copy,hashlib,json,os,random,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
import pytest
from recovery import initialize,ingest,advance,inspect

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def sample(seed):
    rng=random.Random(seed);initial={'x':200+seed,'y':40,'retired':1};rows=initial.copy();events={};commits=[];expected={3:dict(sequence=3,rows=rows.copy(),transactions=[])}
    for seq in range(4,10):
        tx='tx-'+str(seed)+'-'+str(seq);amount=rng.randrange(1,10);ops=[('x',rows['x'],rows['x']-amount),('y',rows['y'],rows['y']+amount)]
        if seq==6:ops.append(('retired',1,None))
        if seq==8:ops.append(('new',None,seed+10))
        groups={}
        for ordinal,(key,before,after) in enumerate(ops):
            shard='s'+str(rng.randrange(3));lsn=100*seq+ordinal;e=dict(lsn=lsn,tx=tx,ordinal=ordinal,key=key,before=before,after=after)
            # Per-shard LSNs, unlike transaction ordinals, are contiguous.
            e['lsn']=len(events.setdefault(shard,[]))+1;events[shard].append(e);groups.setdefault(shard,[]).append(e)
            if after is None:rows.pop(key,None)
            else:rows[key]=after
        parts={s:dict(first=es[0]['lsn'],last=es[-1]['lsn'],sha256=digest(es)) for s,es in groups.items()}
        commits.append(dict(sequence=seq,tx=tx,parts=parts));expected[seq]=dict(sequence=seq,rows=rows.copy(),transactions=[s['tx'] for s in commits])
    return dict(sequence=3,rows=initial),dict(events=events,commits=commits),expected

def call(db,operation,arg=None):
    code="import json,sys,recovery; args=json.loads(sys.argv[1]); print(json.dumps(getattr(recovery,args[0])(*args[1:])))"
    args=[operation,str(db)]+([] if arg is None else [arg])
    result=subprocess.run([sys.executable,'-c',code,json.dumps(args)],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    return json.loads(result.stdout)

@pytest.mark.parametrize('seed',range(10))
def test_shuffled_delivery_checkpoint_and_replay(tmp_path,seed):
    snap,batch,expected=sample(seed);before=copy.deepcopy(batch);db=tmp_path/'ledger.sqlite';initialize(db,snap)
    ingest(db,dict(events={},commits=batch['commits'][::-1]))
    with pytest.raises(ValueError):advance(db,9)
    assert inspect(db)['checkpoint']==expected[3]
    for shard,events in batch['events'].items():ingest(db,dict(events={shard:events[::-1]+events[:2]},commits=[]))
    for target in [5,5,7,9]:assert advance(db,target)==expected[target]
    assert ingest(db,batch)==dict(events=sum(map(len,batch['events'].values())),seals=6)
    assert inspect(db)['checkpoint']==expected[9] and batch==before
    with pytest.raises(ValueError):advance(db,8)

def test_restart_in_separate_processes(tmp_path):
    snap,batch,expected=sample(43);db=tmp_path/'ledger.sqlite';call(db,'initialize',snap);call(db,'ingest',batch)
    assert call(db,'advance',7)==expected[7]
    assert call(db,'initialize',snap)['checkpoint']==expected[7]
    assert call(db,'advance',9)==expected[9]

@pytest.mark.parametrize('kind',['hash','before','ordinal','extra-shard','missing-seal'])
def test_failed_advance_is_atomic(tmp_path,kind):
    snap,batch,expected=sample(55);db=tmp_path/'ledger.sqlite';initialize(db,snap)
    seal=batch['commits'][-1];tx=seal['tx'];shard=next(iter(seal['parts']));event=next(e for e in batch['events'][shard] if e['tx']==tx)
    if kind=='hash':seal['parts'][shard]['sha256']='0'*64
    elif kind=='missing-seal':batch['commits'].pop()
    elif kind=='extra-shard':batch['events']['other']=[dict(lsn=1,tx=tx,ordinal=99,key='z',before=None,after=2)]
    else:
        event['before' if kind=='before' else 'ordinal']=999
        seal['parts'][shard]['sha256']=digest([e for e in batch['events'][shard] if e['tx']==tx])
    ingest(db,batch);prior=inspect(db)
    with pytest.raises(ValueError):advance(db,9)
    assert inspect(db)==prior

def test_conflicting_import_rolls_back_every_addition(tmp_path):
    snap,batch,expected=sample(62);db=tmp_path/'ledger.sqlite';initialize(db,snap);ingest(db,batch);prior=inspect(db)
    shard=next(iter(batch['events']));conflict=copy.deepcopy(batch['events'][shard][0]);conflict['after']=999
    bad=dict(events={'new':[dict(lsn=1,tx='future',ordinal=0,key='z',before=None,after=1)],shard:[conflict]},commits=[])
    with pytest.raises(ValueError):ingest(db,bad)
    assert inspect(db)==prior
    reused=copy.deepcopy(batch['commits'][0]);reused['sequence']=20
    with pytest.raises(ValueError):ingest(db,dict(events={},commits=[reused]))
    assert inspect(db)==prior
    other=copy.deepcopy(batch['commits'][0]);other['tx']='other'
    with pytest.raises(ValueError):ingest(db,dict(events={},commits=[other]))
    assert inspect(db)==prior

def test_applied_transaction_closed_and_uncommitted_ignored(tmp_path):
    snap,batch,expected=sample(82);db=tmp_path/'ledger.sqlite';initialize(db,snap);ingest(db,batch);advance(db,7)
    event=dict(lsn=100,tx=batch['commits'][0]['tx'],ordinal=5,key='z',before=None,after=1)
    with pytest.raises(ValueError):ingest(db,dict(events={'s0':[event]},commits=[]))
    event['tx']='uncommitted';ingest(db,dict(events={'s0':[event]},commits=[]));assert advance(db,9)==expected[9]
    with pytest.raises(ValueError):initialize(db,dict(sequence=0,rows={}))
    assert inspect(db)['checkpoint']==expected[9]

def test_six_concurrent_writers(tmp_path):
    snap,batch,expected=sample(91);db=tmp_path/'ledger.sqlite';initialize(db,snap)
    with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(lambda _:call(db,'ingest',batch),range(6)))
    assert call(db,'advance',9)==expected[9]
    assert inspect(db)['events']==sum(map(len,batch['events'].values()))

def test_cli_rehearsal_is_replayable(tmp_path):
    db=tmp_path/'cli.sqlite';command=[sys.executable,'recovery.py','data/rehearsal.json',str(db)]
    first=subprocess.run(command,capture_output=True,text=True,timeout=20);second=subprocess.run(command,capture_output=True,text=True,timeout=20)
    assert first.returncode==second.returncode==0,(first.stderr,second.stderr)
    assert json.loads(first.stdout)==json.loads(second.stdout)==dict(sequence=15,rows={'cash-a':35,'cash-b':105},transactions=['t11','t12','t13','t14','t15'])
