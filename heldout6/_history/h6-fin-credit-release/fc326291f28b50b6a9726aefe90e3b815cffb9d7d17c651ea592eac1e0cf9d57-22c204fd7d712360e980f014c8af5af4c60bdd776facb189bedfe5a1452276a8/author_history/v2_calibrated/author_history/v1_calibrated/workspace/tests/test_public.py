from funding import analyze

def example():
 return dict(as_of=5,obligations=[dict(id='sale',cents=4,pay_day=1,repaid_day=3)],facilities=[dict(id='bank',cap=4)],collateral=[dict(id='bond',cap=6)],routes=[dict(id='signed',revision=1,known=1,signed=True,void=False,obligation='sale',facility='bank',pledge_cents=6,windows=[dict(from_day=1,until_day=3,pool='bond')])],proposals=[])

def test_complete_release_endpoint():
 r=analyze(example());assert r['complete'] and r['funded_cents']==4
 assert r['usage']==dict(days=[1,3],facilities={'bank':[4,0]},collateral={'bond':[6,0]})
 assert r['owner_review']['proposals']==[]

def test_owner_capacity_is_not_current_authority():
 b=example();b['collateral'][0]['cap']=5;b['proposals']=[dict(id='owner',cost=1,facility_delta={},collateral_delta={'bond':1},routes=[])]
 r=analyze(b);assert not r['complete'] and r['funded_cents']==0
 assert r['owner_review']['proposals']==['owner']
