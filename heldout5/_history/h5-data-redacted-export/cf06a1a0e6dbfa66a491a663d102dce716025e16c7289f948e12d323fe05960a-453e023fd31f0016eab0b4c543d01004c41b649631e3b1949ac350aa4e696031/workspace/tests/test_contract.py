from pipeline import transform

def test_empty_export_has_no_private_rows():
    data={'request':{'tenants':['t'],'purpose':'p','as_of':1,'statuses':['closed'],'k':2},'tickets':[],'bridge':[],'crm':[],'consent':[]}
    assert transform(data)=={'cohorts':[],'regions':[],'excluded':{'deleted':0,'status':0,'consent_at_event':0,'consent_now':0},'blocker_codes':[]}
