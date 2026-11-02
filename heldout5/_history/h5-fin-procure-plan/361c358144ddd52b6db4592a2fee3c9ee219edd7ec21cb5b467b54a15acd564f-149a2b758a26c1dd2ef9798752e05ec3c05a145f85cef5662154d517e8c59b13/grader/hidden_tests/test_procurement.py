import copy,json,random,subprocess,sys,threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from procurement import initialize,apply,snapshot

def seed():return [dict(warehouse=w,sku=k,quantity=q) for w,k,q in [('a','x',5),('a','y',4),('b','x',1),('b','y',1)]]
def manifests():return [dict(id='t',source='a',destination='b',lines={'x':3,'y':2})]
def request(x=3,y=2,routes=['a','b']):return {'needs':{'x':x,'y':y},'routes':{'x':list(routes),'y':list(routes)}}
def reserve(op='r',bid='basket',req=None,at=1,until=10):return dict(operation_id=op,at=at,kind='reserve',basket=bid,until=until,request=req or request())
def receive(op,event,at=1):return dict(operation_id=op,at=at,kind='receive',transfer='t',event=event)
def mutate(op,kind,version,at=2,**kw):return dict(operation_id=op,at=at,kind=kind,basket='basket',expected_version=version,**kw)
def quantities(p):return {(r['warehouse'],r['sku']):(r['on_hand'],r['held'],r['available']) for r in snapshot(p)['stock']}

def test_buffered_transfer_then_exactly_once_source_destination(tmp_path):
    p=str(tmp_path/'db');initialize(p,seed(),manifests());before=quantities(p)
    early=apply(p,receive('early','arrive'));assert early['transfer']=={'id':'t','observed':['arrive'],'status':'waiting'} and quantities(p)==before
    later=apply(p,receive('depart','depart'));assert later['transfer']=={'id':'t','observed':['arrive','depart'],'status':'arrived'}
    assert quantities(p)=={('a','x'):(2,0,2),('a','y'):(2,0,2),('b','x'):(4,0,4),('b','y'):(3,0,3)}
    r=apply(p,reserve(req=request(4,3,['b','a'])));assert r['basket']['allocations']==[{'sku':'x','warehouse':'b','quantity':4},{'sku':'y','warehouse':'b','quantity':3}]
    apply(p,mutate('commit','commit',1));state=quantities(p)
    apply(p,receive('duplicate','arrive',at=2));apply(p,receive('duplicate2','depart',at=2));assert quantities(p)==state
    assert snapshot(p)['history'][0]==early

def test_atomic_transfer_failure_retains_buffer_and_rejected_id(tmp_path):
    p=str(tmp_path/'db');initialize(p,seed(),manifests());apply(p,receive('early','arrive'))
    apply(p,reserve(req=request(1,4,['a','b'])));before=snapshot(p)
    with pytest.raises(ValueError):apply(p,receive('send','depart',at=2))
    assert snapshot(p)==before and before['transfers'][0]['observed']==['arrive']
    apply(p,mutate('release','release',1));out=apply(p,receive('send','depart',at=2));assert out['transfer']['status']=='arrived'
    assert quantities(p)[('a','x')][0]==2 and quantities(p)[('a','y')][0]==2

def test_amend_credits_own_hold_and_failed_amend_keeps_old_plan(tmp_path):
    p=str(tmp_path/'db');initialize(p,seed(),[]);first=apply(p,reserve(req=request(5,4)))
    amended=apply(p,mutate('amend','amend',1,until=8,request=request(6,5,['b','a'])));b=amended['basket']
    assert b['version']==2 and b['allocations']==[{'sku':'x','warehouse':'b','quantity':1},{'sku':'x','warehouse':'a','quantity':5},{'sku':'y','warehouse':'b','quantity':1},{'sku':'y','warehouse':'a','quantity':4}]
    failed=apply(p,mutate('no','amend',2,at=3,until=50,request=request(7,1)));assert failed['result']=='unavailable' and failed['basket']==b
    assert snapshot(p)['baskets'][0]==b and snapshot(p)['clock']==3
    assert snapshot(p)['history'][0]==first
    apply(p,mutate('commit','commit',2,at=4));assert all(x['on_hand']==0 and x['held']==0 for x in snapshot(p)['stock'])

def test_expiration_atomic_rejection_and_unavailable_commits_other_expiry(tmp_path):
    p=str(tmp_path/'db');initialize(p,seed(),manifests());apply(p,reserve(req=request(1,1),until=3));before=snapshot(p)
    with pytest.raises(ValueError):apply(p,mutate('c','commit',1,at=3))
    assert snapshot(p)==before
    apply(p,reserve('other','other',request(1,1),at=2,until=8));original=snapshot(p)['baskets'][1]
    failed=apply(p,dict(mutate('fail','amend',1,at=3,until=9,request=request(99,99)),basket='other'))
    assert failed['basket']==original and snapshot(p)['baskets'][0]['status']=='expired'
    before=snapshot(p)
    bad=reserve('bad','new',{'needs':{'x':99,'y':1},'routes':{'x':['a'],'y':['missing']}},at=9,until=10)
    with pytest.raises(ValueError):apply(p,bad)
    assert snapshot(p)==before
    # An unavailable reserve creates no partial hold, and its basket ID can be tried with a new operation.
    out=apply(p,reserve('big','new',request(99,1),at=3));assert out['basket'] is None
    assert apply(p,reserve('small','new',request(1,1),at=3))['result']=='reserved'

def test_persistent_replay_seed_and_prefix_tuple_order(tmp_path):
    p=str(tmp_path/'db');s=[dict(warehouse=w,sku=k,quantity=2) for w in ['a1','a'] for k in ['m1','m']];initialize(p,s,[])
    assert [(x['warehouse'],x['sku']) for x in snapshot(p)['stock']]==[('a','m'),('a','m1'),('a1','m'),('a1','m1')]
    req={'needs':{'m':1},'routes':{'m':['a1','a']}};cmd=reserve(req=req);r=apply(p,cmd);apply(p,mutate('commit','commit',1,at=4))
    code='import procurement,json;print(json.dumps(procurement.apply('+repr(p)+','+repr(cmd)+')))'
    assert json.loads(subprocess.check_output([sys.executable,'-c',code],text=True))==r
    initialize(p,list(reversed(s)),[]);before=snapshot(p)
    with pytest.raises(ValueError):initialize(p,s[:-1],[])
    with pytest.raises(ValueError):apply(p,dict(cmd,request={'needs':{'m':1},'routes':{'m':['a','a1']}}))
    assert snapshot(p)==before
    r['basket']['request']['needs']['m']=99;before['history'].clear();assert len(snapshot(p)['history'])==2

def test_concurrent_baskets_and_duplicate_receipts(tmp_path):
    p=str(tmp_path/'db');initialize(p,seed(),manifests());barrier=threading.Barrier(6)
    def buy(i):barrier.wait();return apply(p,reserve('r'+str(i),'b'+str(i),request(2,1)))
    with ThreadPoolExecutor(max_workers=6) as pool:out=list(pool.map(buy,range(6)))
    assert sum(x['result']=='reserved' for x in out)==3
    assert sum(x['held'] for x in snapshot(p)['stock'] if x['sku']=='x')==6
    bid=next(x['basket']['id'] for x in out if x['result']=='reserved');barrier=threading.Barrier(2)
    def race(i):
        barrier.wait()
        try:return apply(p,dict(mutate('end'+str(i),'commit' if i==0 else 'release',1),basket=bid))
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=2) as pool:ends=list(pool.map(race,range(2)))
    assert sum(x is not None for x in ends)==1 and len(snapshot(p)['history'])==7
    q=str(tmp_path/'transfers');initialize(q,seed(),manifests());barrier=threading.Barrier(6)
    def delivery(i):barrier.wait();return apply(q,receive('e'+str(i),'depart' if i%2 else 'arrive'))
    with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(delivery,range(6)))
    assert quantities(q)=={('a','x'):(2,0,2),('a','y'):(2,0,2),('b','x'):(4,0,4),('b','y'):(3,0,3)}
    assert len(snapshot(q)['history'])==6

def test_generated_amend_commit_conservation(tmp_path):
    rng=random.Random(812)
    for case in range(5):
        p=str(tmp_path/str(case));s=[dict(warehouse='w',sku=k,quantity=100) for k in ['x','y']];initialize(p,s,[]);used={'x':0,'y':0}
        for i in range(5):
            rid='r'+str(i);first=request(rng.randrange(1,8),rng.randrange(1,8),['w']);second=request(rng.randrange(1,8),rng.randrange(1,8),['w'])
            apply(p,reserve('r'+str(i),rid,first,at=i+1,until=50));out=apply(p,dict(mutate('a'+str(i),'amend',1,at=i+1,until=40,request=second),basket=rid))
            assert out['basket']['request']==second
            commit=rng.choice([True,False]);apply(p,dict(mutate('c'+str(i),'commit' if commit else 'release',2,at=i+1),basket=rid))
            if commit:
                for sku,qty in second['needs'].items():used[sku]+=qty
            assert quantities(p)=={('w',k):(100-used[k],0,100-used[k]) for k in ['x','y']}
        assert len(snapshot(p)['history'])==15
