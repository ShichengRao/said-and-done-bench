import copy,json,random,subprocess,sys,threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from refunds import initialize,apply,snapshot

def seed():return [{'id':'a','merchant':'m','currency':'USD','captured_cents':70,'refund_until':20},{'id':'b','merchant':'m','currency':'USD','captured_cents':80,'refund_until':30}]
def reserve(op='r1',rid='r',cents=100,at=1,until=15,candidates=['a','b']):return dict(operation_id=op,at=at,kind='reserve',refund=rid,merchant='m',currency='USD',cents=cents,until=until,candidates=list(candidates))
def action(op,kind,version,**kw):return dict(operation_id=op,at=2,kind=kind,expected_version=version,**kw)
def test_partial_settle_reversal_expiry_source_balances(tmp_path):
    p=str(tmp_path/'db');initialize(p,seed());cmd=reserve();original=copy.deepcopy(cmd);r=apply(p,cmd)
    assert cmd==original and r['refund']['allocations']==[{'capture':'a','cents':70},{'capture':'b','cents':30}]
    paid=apply(p,action('s','settle',1,refund='r',cents=80));assert paid['refund']['status']=='held' and paid['refund']['version']==2
    rev=apply(p,action('v','reverse',2,settlement='s',cents=75));assert rev['refund']['reversed_cents']==75 and rev['refund']['allocations']==[{'capture':'a','cents':0},{'capture':'b','cents':20}]
    snap=snapshot(p);assert [(c['refunded_cents'],c['held_cents'],c['available_cents']) for c in snap['captures']]==[(0,0,70),(5,20,55)]
    assert snap['settlements'][0]['allocations']==[{'capture':'a','cents':70,'reversed_cents':70},{'capture':'b','cents':10,'reversed_cents':5}]
    assert snap['history'][0]==r and snap['history'][1]==paid
    # An accepted unavailable call commits expiry but never creates a partial refund.
    u=apply(p,reserve('tick','new',200,at=15,until=25));assert u['result']=='unavailable' and u['refund'] is None
    snap=snapshot(p);assert snap['refunds'][0]['status']=='expired' and snap['refunds'][0]['version']==4 and len(snap['refunds'])==1
    assert snap['captures'][1]['available_cents']==75
    apply(p,dict(action('v2','reverse',4,settlement='s',cents=5),at=16));assert snapshot(p)['refunds'][0]['status']=='expired'

def test_unavailable_reusable_identity_candidate_eligibility_and_window(tmp_path):
    p=str(tmp_path/'db');s=seed()+[dict(seed()[0],id='foreign',merchant='other'),dict(seed()[0],id='eur',currency='EUR')];initialize(p,s)
    cmd=reserve(cents=151,candidates=['foreign','eur','b','a']);assert apply(p,cmd)['result']=='unavailable'
    accepted=apply(p,reserve('r2','r',100,at=2,until=25,candidates=['foreign','eur','b','a']))
    assert accepted['refund']['expires']==20 and accepted['refund']['allocations']==[{'capture':'b','cents':80},{'capture':'a','cents':20}]
    before=snapshot(p)
    with pytest.raises(ValueError):apply(p,reserve('bad','other',1,at=20,until=24,candidates=['missing']))
    assert snapshot(p)==before
    after=apply(p,reserve('ok','other',50,at=20,until=24));assert after['refund']['allocations']==[{'capture':'b','cents':50}]
    assert snapshot(p)['refunds'][1]['status']=='expired'

def test_rejected_transition_rolls_back_expiry_and_operation_id(tmp_path):
    p=str(tmp_path/'db');initialize(p,seed());apply(p,reserve(until=3));before=snapshot(p)
    bad=dict(action('x','settle',1,refund='r',cents=10),at=3)
    with pytest.raises(ValueError):apply(p,bad)
    assert snapshot(p)==before
    out=apply(p,dict(bad,at=2));assert out['refund']['version']==2
    before=snapshot(p)
    for cmd in [action('z','settle',1,refund='r',cents=1),action('z','settle',2,refund='r',cents=91),action('z','reverse',2,settlement='x',cents=11),dict(action('z','release',2,refund='r'),at=1)]:
        with pytest.raises(ValueError):apply(p,cmd)
        assert snapshot(p)==before
    apply(p,action('z','release',2,refund='r'));assert snapshot(p)['refunds'][0]['status']=='released'

def test_persistent_replay_immutable_history_and_reinitialization(tmp_path):
    p=str(tmp_path/'db');initialize(p,seed());cmd=reserve();r=apply(p,cmd);apply(p,dict(action('s','settle',1,refund='r',cents=100),at=3))
    code='import refunds,json; print(json.dumps(refunds.apply('+repr(p)+','+repr(cmd)+')))'
    assert json.loads(subprocess.check_output([sys.executable,'-c',code],text=True))==r
    initialize(p,list(reversed(seed())));before=snapshot(p)
    with pytest.raises(ValueError):initialize(p,[dict(seed()[0],captured_cents=999)])
    assert snapshot(p)==before
    with pytest.raises(ValueError):apply(p,dict(cmd,candidates=['b','a']))
    r['refund']['allocations'].clear();before['history'][0]['refund']['id']='forged';assert snapshot(p)['history'][0]['refund']['id']=='r'
    assert len(snapshot(p)['history'])==2

def test_two_settlements_reversal_is_source_specific(tmp_path):
    p=str(tmp_path/'db');initialize(p,seed());apply(p,reserve());apply(p,action('s1','settle',1,refund='r',cents=60));apply(p,action('s2','settle',2,refund='r',cents=40))
    apply(p,action('v','reverse',3,settlement='s2',cents=35));snap=snapshot(p)
    assert [(c['refunded_cents'],c['available_cents']) for c in snap['captures']]==[(60,10),(5,75)]
    with pytest.raises(ValueError):apply(p,action('v2','reverse',4,settlement='s2',cents=6))
    assert snapshot(p)==snap
    apply(p,action('v2','reverse',4,settlement='s1',cents=60));assert snapshot(p)['refunds'][0]['status']=='settled'

def test_concurrency_capacity_replay_and_stale_settlement(tmp_path):
    p=str(tmp_path/'db');initialize(p,seed());barrier=threading.Barrier(6)
    def compete(i):barrier.wait();return apply(p,reserve('o'+str(i),'r'+str(i),40))
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(compete,range(6)))
    assert sum(r['result']=='reserved' for r in results)==3
    s=snapshot(p);assert sum(c['held_cents'] for c in s['captures'])==120 and len(s['history'])==6
    rid=next(r['refund']['id'] for r in results if r['result']=='reserved');barrier=threading.Barrier(2)
    def settle(i):
        barrier.wait()
        try:return apply(p,action('s'+str(i),'settle',1,refund=rid,cents=30))
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(settle,range(2)))
    assert sum(x is not None for x in out)==1
    same=reserve('same','same',1,at=2);barrier=threading.Barrier(5)
    def retry(i):barrier.wait();return apply(p,same)
    with ThreadPoolExecutor(max_workers=5) as pool:out=list(pool.map(retry,range(5)))
    assert all(x==out[0] for x in out) and len(snapshot(p)['history'])==8

def test_generated_single_capture_accounting(tmp_path):
    rng=random.Random(421)
    for case in range(5):
        p=str(tmp_path/str(case));cap=rng.randrange(100,300);initialize(p,[dict(seed()[0],captured_cents=cap,refund_until=100)])
        net=0;held=0;history=0
        for j in range(4):
            amount=rng.randrange(5,20);rid='r'+str(j);apply(p,reserve('a'+str(j),rid,amount,at=j+1,until=90,candidates=['a']));history+=1;held+=amount
            pay=rng.randrange(1,amount+1);apply(p,dict(action('s'+str(j),'settle',1,refund=rid,cents=pay),at=j+1));history+=1;held-=pay;net+=pay
            reverse=rng.randrange(1,pay+1);apply(p,dict(action('v'+str(j),'reverse',2,settlement='s'+str(j),cents=reverse),at=j+1));history+=1;net-=reverse
            if pay<amount:apply(p,dict(action('l'+str(j),'release',3,refund=rid),at=j+1));history+=1;held-=amount-pay
            s=snapshot(p);assert len(s['history'])==history
            assert (s['captures'][0]['refunded_cents'],s['captures'][0]['held_cents'],s['captures'][0]['available_cents'])==(net,held,cap-net-held)
