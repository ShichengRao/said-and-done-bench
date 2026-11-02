from settlement import analyze

def example():
 def r(**payload):return dict(revision=1,known=1,signed=True,void=False,**payload)
 return dict(as_of=1,wallets=[dict(id='A',balance=3),dict(id='B',balance=0)],owners=[r(id='alice',wallet='A'),r(id='bob',wallet='B')],payouts=[r(id='one',source_owner='alice',destination_owner='bob',cents=3,receipt_after=[])],leases=[],proposals=[])

def test_dispatch_and_receipt_are_distinct():
 r=analyze(example());assert r['complete'] and r['plan']==['dispatch:one','receipt:one']
 assert r['reachable_states']==3 and r['final_balances']=={'A':0,'B':3}

def test_proposed_funding_does_not_change_current_wallet():
 b=example();b['wallets'][0]['balance']=2;r=analyze(b)
 assert not r['complete'] and r['settled_cents']==0 and r['owner_review'] is None
