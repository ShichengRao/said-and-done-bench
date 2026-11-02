from pipeline import transform

def test_empty_assignment_is_ready():
    data={'request':{'at':0,'groups':[],'separate':[]},'owners':[],'authority':[],'reservations':[],'proposals':[]}
    assert transform(data)=={'ready':True,'candidates':{},'available_units':{},'assignment':{},'infeasible_core':[],'owner_remedy':None,'blocker_codes':[]}
