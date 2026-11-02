from recognition import analyze

def example():
 def r(**payload):return dict(revision=1,known=1,signed=True,void=False,**payload)
 return dict(as_of=2,period=2,requested_period_cents=2,terms=[r(id='A',effective_period=1,price_cents=5,required_units=2)],receipts=[r(id='old',period=1,units=1,eligible=['A'])],postings=[r(id='posted',period=1,receipt='old',obligation='A',units=1,booked_cents=1)],proposals=[])

def test_half_up_catch_up_keeps_opening():
 r=analyze(example());assert r['opening_cents']==1 and r['complete']
 assert r['chosen']['cumulative_cents']==3 and r['chosen']['period_cents']==2

def test_ticket_is_not_rounded_to_attainable():
 b=example();b['requested_period_cents']=1;r=analyze(b)
 assert not r['complete'] and r['attainable_period_cents']==[2] and r['chosen']['period_cents']==2
