import controller as c
def test_empty_configuration(tmp_path):
 p=str(tmp_path/'db');cfg={'nodes':{},'rack_capacity':{},'services':{},'initial':{},'max_inflight':3}
 assert c.initialize(p,cfg)['version']==0
 assert c.apply(p,{'id':'tick','expected_version':0,'kind':'dispatch'})['created']==[]
