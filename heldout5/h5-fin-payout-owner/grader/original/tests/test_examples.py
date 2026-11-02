from payouts import reconcile
def test_empty():
    b={'as_of':0,'payout_day':0,'settlements':[],'transfers':[],'attestations':[],'proposals':[]}
    assert reconcile(b)['complete'] is True
