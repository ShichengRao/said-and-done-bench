import planner as p
def test_empty_cluster_goal():
 d={'at':0,'nodes':{},'rack_capacity':{},'units':{},'groups':{},'initial':{'positions':{},'images':{}},'target':{},'links':[],'owner_requests':[]}
 assert p.audit(d)['certifiable'] and p.audit(d)['plan']==[]
