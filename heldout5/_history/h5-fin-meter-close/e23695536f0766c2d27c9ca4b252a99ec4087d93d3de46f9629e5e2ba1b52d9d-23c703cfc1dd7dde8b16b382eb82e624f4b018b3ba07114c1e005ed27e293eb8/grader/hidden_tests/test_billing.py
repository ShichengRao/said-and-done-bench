import copy,json,random,sqlite3,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
import pytest
import billing as api

def rate(t='t1',m='m1',v=500,rev=1,known=0):
    return {'id':t,'revision':rev,'known':known,'meter':m,'from':0,'until':30,'tiers':[{'up_to':None,'millicents':v}]}
def usage(i='u1',m='m1',a='a',n=1,rev=1,known=0,at=4,void=False):
    return {'id':i,'revision':rev,'known':known,'account':a,'meter':m,'at':at,'units':n,'void':void}
def cmd(op='op1',time=2,events=None,rates=None,period='p',start=0,end=10):
    return {'operation_id':op,'period':period,'start':start,'end':end,'as_of':time,'usage':[usage()] if events is None else events,'tariffs':[rate()] if rates is None else rates}
def store(tmp_path,name='a.db'):
    p=str(tmp_path/name);api.initialize(p);return p

def invoice_oracle(c,previous=None):
    # Independent materialized winners and per-unit price summation.
    latest=[]
    for name in ['usage','tariffs']:
        visible=[r for r in c[name] if r['known']<=c['as_of']]
        out={}
        for identity in {r['id'] for r in visible}:
            version=max(r['revision'] for r in visible if r['id']==identity)
            out[identity]=next(r for r in visible if r['id']==identity and r['revision']==version)
        latest.append(list(out.values()))
    events,rates=latest;units={};plans={}
    for e in events:
        if e['void'] or not c['start']<=e['at']<c['end']:continue
        r=next(r for r in rates if r['meter']==e['meter'] and r['from']<=e['at']<r['until'])
        k=e['account'],e['meter'],r['id'];units[k]=units.get(k,0)+e['units'];plans[k]=r['tiers']
    raw={}
    for k,n in units.items():
        raw[k]=sum(next(t['millicents'] for t in plans[k] if t['up_to'] is None or unit<=t['up_to']) for unit in range(1,n+1))
    cents={k:value//1000 for k,value in raw.items()}
    for a in {k[0] for k in raw}:
        keys=[k for k in raw if k[0]==a];total=(sum(raw[k] for k in keys)+500)//1000
        for k in sorted(keys,key=lambda k:(-(raw[k]%1000),k[1],k[2]))[:total-sum(cents[k] for k in keys)]:cents[k]+=1
    target={k:{'units':units[k],'amount_cents':cents[k]} for k in units}
    for k in (previous or {}):target.setdefault(k,{'units':0,'amount_cents':0})
    return target

def flatten(invoices):
    return {(i['account'],l['meter'],l['tariff']):{'units':l['units'],'amount_cents':l['amount_cents']} for i in invoices for l in i['lines']}

def test_rounding_cent_reassignment_produces_offsetting_postings(tmp_path):
    p=store(tmp_path);a=cmd(events=[usage(),usage('u2','m2')],rates=[rate(),rate('t2','m2')])
    first=api.close(p,a)
    assert first['invoices']==[{'account':'a','amount_cents':1,'lines':[{'meter':'m1','tariff':'t1','units':1,'amount_cents':1},{'meter':'m2','tariff':'t2','units':1,'amount_cents':0}]}]
    b=copy.deepcopy(a);b.update(operation_id='op2',as_of=5);b['usage'].append(usage(rev=2,known=5,void=True))
    second=api.close(p,b)
    assert second['postings']==[{'account':'a','meter':'m1','tariff':'t1','units_delta':-1,'cents_delta':-1},{'account':'a','meter':'m2','tariff':'t2','units_delta':0,'cents_delta':1}]
    assert second['invoices'][0]['amount_cents']==1
    assert api.snapshot(p)['history'][0]==first

def test_revisions_global_tariff_repricing_and_account_movement(tmp_path):
    p=store(tmp_path);a=cmd(events=[usage(n=6)],rates=[dict(rate(),tiers=[{'up_to':2,'millicents':1500},{'up_to':None,'millicents':250}])])
    first=api.close(p,a);assert first['invoices'][0]['amount_cents']==4
    b=copy.deepcopy(a);b.update(operation_id='op2',as_of=6)
    b['usage'] += [usage(n=6,a='b',rev=2,known=5),usage(n=9,a='c',rev=3,known=9)]
    b['tariffs'].append(rate(rev=2,known=6,v=1000))
    second=api.close(p,b);assert flatten(second['invoices'])=={('a','m1','t1'):{'units':0,'amount_cents':0},('b','m1','t1'):{'units':6,'amount_cents':6}}
    b=copy.deepcopy(b);b.update(operation_id='op3',as_of=8);b['usage'].append(usage(n=6,a='b',rev=3,known=8,at=11))
    assert all(v['amount_cents']==0 for v in api.close(p,b)['invoices'])

def test_atomic_semantic_rejections_and_reusable_rejected_id(tmp_path):
    p=store(tmp_path);a=cmd();api.close(p,a);before=api.snapshot(p)
    b=cmd('retry',5,rates=[])
    with pytest.raises(ValueError):api.close(p,b)
    assert api.snapshot(p)==before
    b['tariffs']=[rate(),rate('other')]
    with pytest.raises(ValueError):api.close(p,b)
    assert api.snapshot(p)==before
    b['tariffs']=[rate()];assert api.close(p,b)['postings']==[]
    before=api.snapshot(p)
    for c in [cmd('x',6,period='q',start=9,end=11),cmd('x',6,end=11),cmd('x',4)]:
        with pytest.raises(ValueError):api.close(p,c)
        assert api.snapshot(p)==before
    c=cmd('x',6,period='q',start=10,end=20,events=[usage(at=11)])
    assert api.close(p,c)['postings'][0]['cents_delta']==1

def test_conflict_detection_before_superseded_filter_and_future_ignored(tmp_path):
    p=store(tmp_path);c=cmd();c['usage'] += [usage(n=2),usage(rev=2,known=0)]
    with pytest.raises(ValueError):api.close(p,c)
    assert api.snapshot(p)['history']==[]
    c=cmd();c['usage'] += [usage(n=2,rev=5,known=9),usage(n=3,rev=5,known=9)]
    assert api.close(p,c)['invoices'][0]['amount_cents']==1

def test_durable_replay_precedes_clock_and_outputs_detached(tmp_path):
    p=store(tmp_path);c=cmd();before=copy.deepcopy(c);original=api.close(p,c);saved=copy.deepcopy(original)
    assert c==before;original['postings'].clear()
    api.close(p,cmd('later',9))
    code='import json,sys,billing; print(json.dumps(billing.close(sys.argv[1],json.loads(sys.argv[2]))))'
    out=subprocess.run([sys.executable,'-c',code,p,json.dumps(c)],capture_output=True,text=True,check=True)
    assert json.loads(out.stdout)==saved
    snapshot=api.snapshot(p);snapshot['history'][0]['postings'].clear();api.initialize(p)
    assert api.snapshot(p)['history'][0]==saved
    changed=copy.deepcopy(c);changed['as_of']=10
    with pytest.raises(ValueError):api.close(p,changed)
    with sqlite3.connect(p) as db:assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)

def test_concurrent_replays_and_differential_postings(tmp_path):
    p=store(tmp_path);c=cmd();gate=Barrier(6)
    def call(_):gate.wait(timeout=5);return api.close(p,c)
    with ThreadPoolExecutor(max_workers=6) as pool:rs=list(pool.map(call,range(6)))
    assert all(r==rs[0] for r in rs);assert len(api.snapshot(p)['history'])==1
    gate=Barrier(4)
    def changed(i):
        x=cmd('later'+str(i),8,events=[usage(n=i+2,rev=2,known=8)])
        gate.wait(timeout=5);return api.close(p,x)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(changed,range(4)))
    snap=api.snapshot(p);assert len(snap['history'])==5
    assert sum(z['cents_delta'] for h in snap['history'] for z in h['postings'])==snap['invoices']['p'][0]['amount_cents']
    assert sum(z['units_delta'] for h in snap['history'] for z in h['postings'])==snap['invoices']['p'][0]['lines'][0]['units']

def test_generated_correction_sequences_independent_prices(tmp_path):
    rng=random.Random(61703)
    for case in range(5):
        p=store(tmp_path,str(case)+'.db');events=[usage('u'+str(i),'m'+str(i%2),'a'+str(i%2),rng.randrange(0,8)) for i in range(6)]
        rates=[dict(rate('t'+str(i),'m'+str(i)),tiers=[{'up_to':3,'millicents':rng.randrange(1,9)*125},{'up_to':None,'millicents':rng.randrange(0,8)*125}]) for i in range(2)]
        prior={};journal={}
        for step in range(1,9):
            if step>1:
                chosen=rng.choice(events);new=copy.deepcopy(chosen);new.update(revision=max(e['revision'] for e in events if e['id']==new['id'])+1,known=step,units=rng.randrange(0,8),account='a'+str(rng.randrange(3)),void=rng.random()<.2,at=rng.randrange(0,14));events.append(new)
            c=cmd('op'+str(step),step,events=copy.deepcopy(events),rates=copy.deepcopy(rates));rng.shuffle(c['usage'])
            expected=invoice_oracle(c,prior);original=copy.deepcopy(c);got=api.close(p,c)
            assert c==original;assert flatten(got['invoices'])==expected
            for row in got['postings']:
                k=(row['account'],row['meter'],row['tariff']);v=journal.setdefault(k,{'units':0,'amount_cents':0});v['units']+=row['units_delta'];v['amount_cents']+=row['cents_delta']
            assert {k:journal.get(k,{'units':0,'amount_cents':0}) for k in expected}==expected
            prior=expected


def test_prefix_identifiers_obey_tuple_order(tmp_path):
    p=store(tmp_path)
    events=[usage('u'+str(i),m=m,a=a) for i,(a,m) in enumerate([('a1','m1'),('a','m1'),('a1','m'),('a','m')])]
    first=api.close(p,cmd(events=events,rates=[rate('t','m',1000),rate('t1','m1',1000)]))
    assert [i['account'] for i in first['invoices']]==['a','a1']
    assert [[(l['meter'],l['tariff']) for l in i['lines']] for i in first['invoices']]==[[('m','t'),('m1','t1')],[('m','t'),('m1','t1')]]
    assert [(p['account'],p['meter'],p['tariff']) for p in first['postings']]==[('a','m','t'),('a','m1','t1'),('a1','m','t'),('a1','m1','t1')]
    later=api.close(p,cmd('later',3,events=[],rates=[]))
    assert [(p['account'],p['meter']) for p in later['postings']]==[('a','m'),('a','m1'),('a1','m'),('a1','m1')]
    assert [i['account'] for i in api.snapshot(p)['invoices']['p']]==['a','a1']
