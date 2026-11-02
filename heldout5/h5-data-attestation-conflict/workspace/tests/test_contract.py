from pipeline import transform

def test_empty_sealed_interval():
    data={'manifest':{'count':0,'root':'0'*64},'receipts':[],'artifacts':[],'ownership':[],'requests':[],'attempts':[],'memberships':[],'policy':[],'replacements':[]}
    assert transform(data)=={'certifiable':True,'receipt_checks':[],'violations':[],'safe_replays':[],'blocker_codes':[]}
