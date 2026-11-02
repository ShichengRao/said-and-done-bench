import copy,json,itertools,random,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path
from threading import Barrier
import pytest
import billing as api

def config():
    return {'periods':[{'id':'p1','start':0,'end':10,'cycle':'month'},{'id':'p2','start':10,'end':20,'cycle':'month'}],
            'meters':[{'id':'a','account':'alice','pool':'shared'},{'id':'b','account':'bob','pool':'shared'}],
            'pools':[{'id':'shared','tiers':[{'up_to':5,'millicents':1000},{'up_to':None,'millicents':250}]}]}

def reading(identity,meter,at,counter,revision=1,known=0,epoch='e1',void=False):
    return dict(id=identity,revision=revision,known=known,meter=meter,epoch=epoch,at=at,counter=counter,void=void)

def command(op,rows,as_of=1):return dict(operation_id=op,as_of=as_of,readings=rows)

def seeded(tmp_path,cfg=None,name='billing.db'):
    path=str(tmp_path/name);api.initialize(path,config() if cfg is None else cfg);return path

def oracle(cfg,deliveries,as_of,previous=()):
    # Independent Fraction allocation and literal per-unit progressive pricing.
    # Generated fixtures are well-formed; rejection is checked separately.
    selected=[]
    for identity in {r['id'] for r in deliveries}:
        visible=[r for r in deliveries if r['id']==identity and r['known']<=as_of]
        if visible:
            winner=max(visible,key=lambda r:r['revision'])
            if not winner['void']:selected.append(winner)
    units={}
    for meter in cfg['meters']:
        for epoch in {r['epoch'] for r in selected if r['meter']==meter['id']}:
            ordered=sorted([r for r in selected if r['meter']==meter['id'] and r['epoch']==epoch],key=lambda r:r['at'])
            for left,right in zip(ordered,ordered[1:]):
                pieces=[]
                for p in cfg['periods']:
                    overlap=len(set(range(left['at'],right['at'])) & set(range(p['start'],p['end'])))
                    if overlap:pieces.append((p['id'],Fraction((right['counter']-left['counter'])*overlap,right['at']-left['at'])))
                allocated={p:int(value) for p,value in pieces}
                residual=right['counter']-left['counter']-sum(allocated.values())
                for p,value in sorted(pieces,key=lambda pair:(-(pair[1]-int(pair[1])),pair[0]))[:residual]:allocated[p]+=1
                for p,n in allocated.items():
                    key=(p,meter['account'],meter['id']);units[key]=units.get(key,0)+n
    costs={k:0 for k in units}
    for cycle in {p['cycle'] for p in cfg['periods']}:
        for pool in cfg['pools']:
            keys=[k for k in units if next(p['cycle'] for p in cfg['periods'] if p['id']==k[0])==cycle
                  and next(m['pool'] for m in cfg['meters'] if m['id']==k[2])==pool['id']]
            total=sum(units[k] for k in keys)
            if not total:continue
            amount=sum(next(t['millicents'] for t in pool['tiers'] if t['up_to'] is None or n<=t['up_to']) for n in range(1,total+1))
            shares={k:Fraction(amount*units[k],1000*total) for k in keys}
            for k in keys:costs[k]=int(shares[k])
            rounded=int(Fraction(amount,1000)+Fraction(1,2))
            for k in sorted(keys,key=lambda k:(-(shares[k]-int(shares[k])),k))[:rounded-sum(costs[k] for k in keys)]:costs[k]+=1
    target={k:dict(period=k[0],account=k[1],meter=k[2],units=units[k],cents=costs[k]) for k in units}
    for r in previous:target.setdefault((r['period'],r['account'],r['meter']),dict(r,units=0,cents=0))
    return [target[k] for k in sorted(target)]

def test_canonical_history_needs_adjacent_reconstruction_and_cross_period_repricing(tmp_path):
    example=json.loads(Path('data/request.json').read_text());path=seeded(tmp_path,example['config']);retained=[];prior=[];responses=[]
    for cmd in example['commands']:
        retained.extend(cmd['readings']);result=api.close(path,cmd)
        wanted=oracle(example['config'],retained,cmd['as_of'],prior)
        assert result['targets']==wanted
        old={(r['period'],r['account'],r['meter']):r for r in prior};postings=[]
        for r in wanted:
            key=r['period'],r['account'],r['meter'];before=old.get(key,dict(units=0,cents=0))
            u,c=r['units']-before['units'],r['cents']-before['cents']
            if u or c:postings.append(dict(period=key[0],account=key[1],meter=key[2],units_delta=u,cents_delta=c))
        assert result==dict(operation_id=cmd['operation_id'],as_of=cmd['as_of'],targets=wanted,postings=postings)
        responses.append(copy.deepcopy(result));prior=wanted
    snap=api.snapshot(path)
    assert snap['history']==responses and snap['targets']==prior and snap['clock']==7
    assert responses[0]['targets']==[
      {'period':'p1','account':'alice','meter':'a','units':4,'cents':2},
      {'period':'p1','account':'bob','meter':'b','units':3,'cents':2},
      {'period':'p2','account':'alice','meter':'a','units':4,'cents':2},
      {'period':'p2','account':'bob','meter':'b','units':2,'cents':1}]
    assert responses[1]['postings']==[
      {'period':'p1','account':'alice','meter':'a','units_delta':2,'cents_delta':1},
      {'period':'p2','account':'alice','meter':'a','units_delta':-2,'cents_delta':-1}]
    assert all(r['cents']==0 for r in prior if r['meter']=='b')
    assert sum(r['cents'] for r in prior)==6

@pytest.mark.parametrize('seed',range(10))
def test_independent_fraction_oracle_and_future_delivery_activation(tmp_path,seed):
    rng=random.Random(seed);cfg=config();cfg['periods']=[dict(id=f'p{i}',start=a,end=b,cycle='c0' if i<2 else 'c1') for i,(a,b) in enumerate([(0,4),(4,10),(10,17)])]
    cfg['pools'][0]['tiers']=[dict(up_to=3,millicents=rng.randint(200,1900)),dict(up_to=None,millicents=rng.randint(50,700))]
    rows=[]
    for m in ['a','b']:
        middle=rng.randint(1,16);n=rng.randint(2,12);mid=rng.randint(0,n)
        rows.extend([reading(m+'0',m,0,3),reading(m+'1',m,middle,3+mid),reading(m+'2',m,17,3+n),
                     reading(m+'1',m,middle,3+rng.randint(0,n),revision=2,known=5)])
    rng.shuffle(rows);path=seeded(tmp_path,cfg)
    a=api.close(path,command('initial',rows+rows[:2],1));assert a['targets']==oracle(cfg,rows,1)
    b=api.close(path,command('activate',[],5));assert b['targets']==oracle(cfg,rows,5,a['targets'])
    assert api.snapshot(path)['delivery_count']==len(rows)
    assert api.close(path,command('same',list(reversed(rows)),6))['postings']==[]

def test_revisions_resolve_before_meter_epoch_time_or_void_filtering(tmp_path):
    cfg=config();rows=[reading('x','a',0,10),reading('y','a',20,18),reading('q','b',0,100),reading('z','b',20,106)]
    path=seeded(tmp_path,cfg);first=api.close(path,command('one',rows))
    delta=[reading('y','b',20,104,revision=2,known=3),reading('z','b',20,106,revision=2,known=3,void=True)]
    second=api.close(path,command('move',delta,3))
    assert second['targets']==oracle(cfg,rows+delta,3,first['targets'])
    assert all(r['units']==r['cents']==0 for r in second['targets'] if r['meter']=='a')

@pytest.mark.parametrize('kind',['decrease','same-time','overlap','gap','conflict','clock'])
def test_rejection_rolls_back_delivery_history_clock_and_identity(tmp_path,kind):
    cfg=config()
    if kind=='gap':cfg['periods'][1]['start']=11
    path=seeded(tmp_path,cfg);good=command('base',[reading('x','a',0,0),reading('y','a',10,3)])
    api.close(path,good);before=api.snapshot(path)
    rows={'decrease':[reading('z','a',20,2)],'same-time':[reading('z','a',10,3)],
          'overlap':[reading('z','a',5,0,epoch='e2'),reading('q','a',15,2,epoch='e2')],
          'gap':[reading('z','a',20,4)],'conflict':[reading('y','a',10,4)],'clock':[]}[kind]
    bad=command('retryable',rows,0 if kind=='clock' else 2)
    with pytest.raises(ValueError):api.close(path,bad)
    assert api.snapshot(path)==before
    assert api.close(path,command('retryable',[],2))['postings']==[]

def test_superseded_duplicate_conflicts_are_not_hidden_by_latest_revision(tmp_path):
    path=seeded(tmp_path);before=api.snapshot(path)
    rows=[reading('x','a',0,0),reading('x','a',0,1),reading('x','a',0,2,revision=2)]
    with pytest.raises(ValueError):api.close(path,command('bad',rows))
    assert api.snapshot(path)==before

def test_replay_precedes_clock_and_seed_reinitialization_uses_original_config(tmp_path):
    cfg=config();path=seeded(tmp_path,cfg);cmd=command('first',[reading('x','a',0,0),reading('y','a',20,7)])
    first=api.close(path,cmd);api.close(path,command('later',[],9));before=api.snapshot(path)
    assert api.close(path,copy.deepcopy(cmd))==first
    changed=copy.deepcopy(cmd);changed['as_of']=10
    with pytest.raises(ValueError):api.close(path,changed)
    reordered={k:list(reversed(v)) for k,v in cfg.items()};assert api.initialize(path,reordered) is None
    assert api.snapshot(path)==before
    altered=copy.deepcopy(cfg);altered['pools'][0]['tiers'][0]['millicents']+=1
    with pytest.raises(ValueError):api.initialize(path,altered)
    assert api.snapshot(path)==before

def test_restart_and_returned_value_isolation(tmp_path):
    cfg=config();path=seeded(tmp_path,cfg);cmd=command('a',[reading('x','a',0,0),reading('y','a',20,7)]);saved=copy.deepcopy(cmd)
    first=api.close(path,cmd);expected=copy.deepcopy(first);cmd['readings'][0]['counter']=999;first['targets'][0]['units']=999
    code='import json,billing; print(json.dumps(billing.snapshot('+repr(path)+')))'
    run=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=30);assert run.returncode==0,run.stderr
    assert json.loads(run.stdout)['history']==[expected] and saved!=cmd
    assert api.close(path,saved)==expected

def test_concurrent_incremental_sources_and_exact_replay(tmp_path):
    path=seeded(tmp_path);barrier=Barrier(4)
    cmds=[command('a',[reading('a0','a',0,0),reading('a1','a',20,8)],10),command('b',[reading('b0','b',0,0),reading('b1','b',20,5)],10)]
    def call(i):barrier.wait();return api.close(path,copy.deepcopy(cmds[i%2]))
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(call,range(4)))
    assert results[0]==results[2] and results[1]==results[3]
    snap=api.snapshot(path)
    assert len(snap['history'])==2 and snap['delivery_count']==4
    assert snap['targets']==oracle(config(),cmds[0]['readings']+cmds[1]['readings'],10)
