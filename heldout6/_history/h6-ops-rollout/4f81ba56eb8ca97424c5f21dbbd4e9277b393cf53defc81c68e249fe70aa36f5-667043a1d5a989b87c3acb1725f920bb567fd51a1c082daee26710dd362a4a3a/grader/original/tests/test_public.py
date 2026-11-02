import controller as c

def test_empty_configuration(tmp_path):
    cfg={'nodes':[],'capacity':0,'max_handoffs':2,'initial':{}}
    p=str(tmp_path/'db')
    assert c.initialize(p,cfg)['version']==0
    assert c.apply(p,{'id':'tick','expected_version':0,'kind':'dispatch'})['created']==[]
