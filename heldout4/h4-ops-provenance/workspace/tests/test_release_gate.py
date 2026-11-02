from release_gate import closure

def test_no_requested_release():
    assert closure({'policy':{'at':0},'requested':[],'releases':[],'artifacts':{}})==[]
