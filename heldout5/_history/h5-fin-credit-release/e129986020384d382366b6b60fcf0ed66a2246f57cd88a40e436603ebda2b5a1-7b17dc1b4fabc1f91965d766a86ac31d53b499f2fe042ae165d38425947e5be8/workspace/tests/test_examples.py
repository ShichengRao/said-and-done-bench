from funding import analyze

def test_no_obligations():
    result=analyze({'as_of':0,'groups':{},'facilities':[],'obligations':[],'holds':[],'approvals':[],'proposals':[]})
    assert result=={'requested_cents':0,'complete':True,'funded_cents':0,'schedule':[],'unfunded':[],'usage':{'days':[],'facilities':{},'groups':{}},'owner_review':{'cost':0,'proposals':[],'schedule':[]}}
