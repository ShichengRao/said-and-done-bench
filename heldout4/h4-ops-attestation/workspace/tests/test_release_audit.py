from release_audit import audit

def test_empty_window():
    assert audit({'grants':[],'tokens':[],'requests':[],'approvals':[],'events':[]})=={'can_attest':True,'production_deployments':0,'violations':[],'deployments':[]}
