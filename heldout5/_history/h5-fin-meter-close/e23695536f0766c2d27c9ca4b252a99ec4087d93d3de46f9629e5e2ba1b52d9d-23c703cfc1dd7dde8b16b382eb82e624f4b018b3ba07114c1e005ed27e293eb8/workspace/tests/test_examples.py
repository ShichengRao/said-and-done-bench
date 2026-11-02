from billing import initialize,snapshot,close

def test_empty_store_and_close(tmp_path):
    p=str(tmp_path/'b.db');initialize(p)
    c={'operation_id':'a','period':'p','start':0,'end':1,'as_of':0,'usage':[],'tariffs':[]}
    r=close(p,c)
    assert r=={'operation_id':'a','period':'p','as_of':0,'invoices':[],'postings':[]}
    assert snapshot(p)['history']==[r]
