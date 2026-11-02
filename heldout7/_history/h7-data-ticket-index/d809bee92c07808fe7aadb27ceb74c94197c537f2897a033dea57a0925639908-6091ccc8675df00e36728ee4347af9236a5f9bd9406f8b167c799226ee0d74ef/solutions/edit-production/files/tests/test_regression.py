import copy
import pytest
from ticket_index.projection import Projection
from ticket_index.seal import digest
INITIAL={'folders':{'r':{'parent':None,'acl':['g']}},'documents':{},'memberships':{'u':['g']}}
def messages(e,ops):return [{'kind':'fragment','epoch':e,'part':0,'parts':1,'operations':ops},{'kind':'seal','epoch':e,'parts':1,'digests':[digest(ops)]}]
def test_unlocks_all_sealed_successors(tmp_path):
    p=Projection(tmp_path/'db',INITIAL);p.ingest(messages(2,[]));assert p.status()['published']==0
    p.ingest(messages(1,[]));assert Projection(tmp_path/'db').status()=={'published':2,'pending':[]}
def test_batch_failure_retains_no_earlier_revision(tmp_path):
    p=Projection(tmp_path/'db',INITIAL);bad=messages(1,[])+messages(2,[{'kind':'put_folder','id':'r','parent':'r','acl':[]}]);before=copy.deepcopy(bad)
    with pytest.raises(ValueError):p.ingest(bad)
    assert bad==before and Projection(tmp_path/'db').status()=={'published':0,'pending':[]}
    p.ingest(messages(1,[]));assert p.status()['published']==1
