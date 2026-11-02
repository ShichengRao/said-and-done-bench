from ledger import apply_batch

def test_capture():
    s={'seen':{},'captures':{},'refunds':{},'balances':{}}
    e={'merchant':'elm','id':'c1','sequence':1,'kind':'capture','reference':None,'cents':100}
    assert apply_batch(s,[e])['balances']=={'elm':100}
    assert s['balances']=={}
