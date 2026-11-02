from recovery import restore

def test_uncommitted_writes_do_not_change_checkpoint():
    bundle={'snapshot':{'sequence':0,'rows':{'balance':10}},'commits':[], 'segments':{'east':[{'lsn':1,'tx':'pending','ordinal':0,'key':'balance','before':10,'after':0}]}}
    assert restore(bundle,0)=={'sequence':0,'rows':{'balance':10},'transactions':[]}
