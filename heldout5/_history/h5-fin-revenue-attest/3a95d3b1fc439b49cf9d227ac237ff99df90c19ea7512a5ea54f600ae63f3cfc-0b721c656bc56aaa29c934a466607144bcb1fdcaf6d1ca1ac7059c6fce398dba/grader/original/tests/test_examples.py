from revenue import rollforward
def test_empty():
    b={'as_of':0,'open_day':0,'close_day':1,'requested_cents':0,'terms':[],'progress':[],'invoices':[],'posted':[],'proposals':[]}
    assert rollforward(b)['complete'] is True
