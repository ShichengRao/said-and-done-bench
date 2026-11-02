import procurement as p
def test_empty_store(tmp_path):
 db=str(tmp_path/'db');cat={'warehouses':{},'recipes':{},'stock':[]};assert p.initialize(db,cat)['clock']==0
 assert p.apply(db,{'operation_id':'tick','at':1,'kind':'tick'})['result']=='ticked'
