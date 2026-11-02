from pipeline import transform

def test_unaffected_payload_is_preserved():
    version={'version':'v','object':'o','parents':[],'identities':[],'payload':{'x':[1,2]}}
    data={'catalog':{'watermark':0,'cutover':1,'at':1,'versions':[version],'heads':{'o':'v'}},'changes':[],'identity':[],'requests':[],'holds':[]}
    assert transform(data)=={'survivors':[version],'suppressed':[],'purge_versions':[],'retained_for_hold':[],'tainted_versions':[],'blocker_codes':[]}
