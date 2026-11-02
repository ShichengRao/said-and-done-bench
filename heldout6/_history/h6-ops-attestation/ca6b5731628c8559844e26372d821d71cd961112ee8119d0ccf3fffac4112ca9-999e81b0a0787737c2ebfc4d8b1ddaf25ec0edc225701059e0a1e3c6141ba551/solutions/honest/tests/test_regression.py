import release_audit as a
def test_empty_history_has_initial_state():
 d={'initial':{},'scope':[],'keys':{},'grants':[],'operations':[],'owner_requests':[]}
 assert a.audit(d)['certifiable'] is True

def test_empty_history_certificate_count():
 d={'initial':{'service':0},'scope':[],'keys':{},'grants':[],'operations':[],'owner_requests':[]}
 assert a.audit(d)['history']['reachable_count']==1
