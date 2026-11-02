import copy,random
import pytest
from ledger import apply_batch

def empty():return {'seen':{},'captures':{},'refunds':{},'balances':{}}
def e(i,s,k='capture',ref=None,n=100,m='elm'):return dict(merchant=m,id=i,sequence=s,kind=k,reference=ref,cents=n)
def batch():return [e('c',1,n=1000),e('r',2,'refund','c',700),e('v',3,'reverse','r',700),e('r2',4,'refund','c',900)]
def test_reordered_replay_reversal_and_released_capacity():
    original=batch();x=copy.deepcopy(original)
    out=apply_batch(empty(),list(reversed(x))+[x[1]])
    assert out['balances']=={'elm':100}
    assert out['captures']=={'elm:c':{'cents':1000,'refunded':900}}
    assert out['refunds']=={'elm:r':{'capture':'elm:c','cents':700,'reversed':True},'elm:r2':{'capture':'elm:c','cents':900,'reversed':False}}
    assert len(out['seen'])==4 and x==original
    before=copy.deepcopy(out)
    assert apply_batch(out,original)==out and out==before

def test_cross_merchant_ids_and_sequences():
    events=[e('c',1,n=200,m='elm'),e('c',1,n=300,m='pine'),e('r',2,'refund','c',120,m='pine')]
    out=apply_batch(empty(),events)
    assert out['balances']=={'elm':200,'pine':180} and len(out['seen'])==3

def test_atomic_rejection_after_valid_first_event():
    s=apply_batch(empty(),[e('c',1)])
    old=copy.deepcopy(s);events=[e('d',2,n=300),e('r',3,'refund','c',101)]
    with pytest.raises(ValueError):apply_batch(s,events)
    assert s==old

@pytest.mark.parametrize('events',[
 [e('c',1),e('c',1,n=101)], [e('c',1),e('d',1)],
 [e('r',1,'refund','missing')], [e('c',1),e('r',2,'refund','c'),e('v',3,'reverse','r',99)],
 [e('c',1),e('r',2,'refund','c'),e('v',3,'reverse','r'),e('v2',4,'reverse','r')],
 [e('c',2),e('r',1,'refund','c')], [e('c',1,m='pine'),e('r',2,'refund','c',m='elm')],
 [e('c',True)], [e('c',1,n=True)], [e('c',1,n=0)], [e('c',1,ref='bad')], [e('c',1,m='x:y')]])
def test_invalid(events):
    s=empty()
    with pytest.raises(ValueError):apply_batch(s,events)
    assert s==empty()

def test_persisted_sequence_and_conflicting_replay():
    s=apply_batch(empty(),[e('c',4)])
    for events in ([e('d',3)],[e('c',4,n=101)]):
        with pytest.raises(ValueError):apply_batch(s,events)

def test_deterministic_batches():
    rng=random.Random(714)
    for _ in range(35):
        n=rng.randint(1,10000);a=rng.randint(1,n);b=rng.randint(1,n)
        events=[e('c',1,n=n),e('r',2,'refund','c',a),e('v',3,'reverse','r',a),e('s',4,'refund','c',b)]
        rng.shuffle(events)
        whole=apply_batch(empty(),events)
        split=apply_batch(apply_batch(empty(),[e('c',1,n=n),e('r',2,'refund','c',a)]),[e('s',4,'refund','c',b),e('v',3,'reverse','r',a)])
        assert whole==split and whole['balances']=={'elm':n-b}
