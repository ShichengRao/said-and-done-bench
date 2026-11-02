import billing

def test_empty_store_and_close(tmp_path):
    p=str(tmp_path/'empty.db');cfg={'periods':[],'meters':[],'pools':[]}
    assert billing.initialize(p,cfg) is None
    response={'operation_id':'empty','as_of':1,'targets':[],'postings':[]}
    assert billing.close(p,dict(operation_id='empty',as_of=1,readings=[]))==response
    assert billing.snapshot(p)==dict(clock=1,config=cfg,delivery_count=0,targets=[],history=[response])
