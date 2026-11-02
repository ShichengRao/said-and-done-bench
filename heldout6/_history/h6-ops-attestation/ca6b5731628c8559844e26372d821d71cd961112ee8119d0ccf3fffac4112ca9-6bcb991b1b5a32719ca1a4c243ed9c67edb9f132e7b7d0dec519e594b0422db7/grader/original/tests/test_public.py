import release_audit as a
def test_empty_scope_is_certifiable():
 d={'initial':{},'scope':[],'keys':{},'grants':[],'operations':[],'owner_requests':[]}
 assert a.audit(d)['certifiable'] is True
