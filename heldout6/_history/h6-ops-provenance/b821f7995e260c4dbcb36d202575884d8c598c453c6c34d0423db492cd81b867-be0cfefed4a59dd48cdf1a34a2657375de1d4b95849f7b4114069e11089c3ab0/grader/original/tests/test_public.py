import release_gate as g
def test_empty_trust_store(tmp_path):
 p=str(tmp_path/'db');assert g.initialize(p,{})=={'version':0,'at':-1,'repositories':{}}
