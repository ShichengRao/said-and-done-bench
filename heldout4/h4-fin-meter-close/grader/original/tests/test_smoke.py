from billing import close_month

def test_one_account():
    e={'event_id':'a','revision':1,'account':'cedar','at':'2026-09-10T00:00:00Z','units':2,'void':False}
    assert close_month([e],[{'up_to':None,'rate_millicents':1000}],'2026-09-01T00:00:00Z','2026-10-01T00:00:00Z') == [{'account':'cedar','units':2,'amount_cents':2}]
