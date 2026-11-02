import refunds as r
def test_empty_store(tmp_path):
 p=str(tmp_path/'db');assert r.initialize(p,[])['clock']==0
 assert r.apply(p,{'operation_id':'tick','at':1,'kind':'tick'})['result']=='ticked'
