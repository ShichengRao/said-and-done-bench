from procurement import initialize,snapshot
def test_empty(tmp_path):
    p=str(tmp_path/'db');initialize(p,[],[])
    assert snapshot(p)=={'clock':0,'stock':[],'baskets':[],'transfers':[],'history':[]}
