from rollout import plan

def test_start_replacement_before_draining_last_replica():
    spec={'nodes':[{'id':'a','zone':'east','eligible':True,'maintenance':False},{'id':'b','zone':'west','eligible':True,'maintenance':False}], 'initial':{'a':'old'},'min_ready':1,'max_total':2,'min_zones':1,'desired':1}
    assert plan(spec)==[{'op':'start','node':'b'},{'op':'stop','node':'a'}]
