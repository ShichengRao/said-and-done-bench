import recovery as r
def test_empty_recovery(tmp_path):
 p=str(tmp_path/'db');a={'frontier':{'s':0},'values':{'s':{}},'applied':[]}
 assert r.initialize(p,a)['version']==0
 assert r.advance(p,'first',0,{'s':0})['order']==[]
