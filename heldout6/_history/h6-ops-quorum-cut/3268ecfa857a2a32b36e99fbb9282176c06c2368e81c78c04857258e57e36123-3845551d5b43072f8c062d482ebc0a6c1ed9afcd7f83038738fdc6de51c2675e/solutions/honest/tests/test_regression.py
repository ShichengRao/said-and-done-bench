import planner as p
def test_empty_cluster_certificate():
 d={'at':0,'nodes':{},'rack_capacity':{},'units':{},'groups':{},'initial':{'positions':{},'images':{}},'target':{},'links':[],'owner_requests':[]}
 assert p.audit(d)['certifiable'] and p.audit(d)['plan']==[]

def test_empty_cluster_one_state():
 d={'at':0,'nodes':{},'rack_capacity':{},'units':{},'groups':{},'initial':{'positions':{},'images':{}},'target':{},'links':[],'owner_requests':[]}
 assert p.audit(d)['reachable_count']==1

def test_accepted_copy_requires_duplicate_bytes():
 d={'at':0,'nodes':{'left':{'rack':'r','zone':'a','capacity':2},'right':{'rack':'r','zone':'b','capacity':2}},'rack_capacity':{'r':3},'units':{'unit':{'group':'g','size':2,'allowed_final':['right']}},'groups':{'g':{'quorum':1,'min_zones':1}},'initial':{'positions':{'unit':'left'},'images':{'unit':'old'}},'target':{'unit':'right'},'links':[{'id':'copy','revision':1,'source':'left','target':'right','enabled':True,'valid_from':0,'valid_to':1}],'owner_requests':[]}
 assert p.audit(d)['plan'] is None
 d['rack_capacity']['r']=4
 assert p.audit(d)['plan']==[['start','unit','right'],['ready','unit','right'],['commit','unit','right']]
