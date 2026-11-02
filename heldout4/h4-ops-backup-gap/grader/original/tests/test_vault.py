from vault import audit

def test_empty_vault():
    spec={'catalog':[],'objects':{},'tenant':'t','timeline':'x','target':1,'allowed_regions':[],'key_inventory':[]}
    assert audit(spec)['complete'] is False
