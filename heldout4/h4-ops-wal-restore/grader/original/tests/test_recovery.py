from recovery import restore

def test_empty_checkpoint():
    b={'snapshot':{'sequence':3,'rows':{'cash':9}},'segments':{},'commits':[]}
    assert restore(b,3)=={'sequence':3,'rows':{'cash':9},'transactions':[]}
