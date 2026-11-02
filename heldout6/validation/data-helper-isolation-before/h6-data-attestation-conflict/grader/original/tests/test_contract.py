from pipeline import transform


def sample():
    return {'evidence':{'documents':{'d':{'owner':'x','version':2}},'slots':{'root':{'generation':0,'node':'cap0'}},'capabilities':[{'id':'cap0','slot':'root','parent':None,'owner':'x','issuer':'x','audience':'team','delegate':False}],'streams':[[{'id':'cache','kind':'copy','source':{'kind':'document','id':'d'},'slot':'root'},{'id':'delivered','kind':'receipt','copy':'cache','audience':'team'}]],'before':[]},'proposals':[]}


def test_public_example():
    assert transform(sample())=={'ready':True,'classification':'verified_safe','serialization_count':1,'safe_count':1,'unsafe_count':0,'first_safe_order':['cache','delivered'],'first_unsafe':None,'owner_request':{'proposal_ids':[],'cost':0,'serialization_count':1,'first_order':['cache','delivered']},'blocker_codes':[]}


def test_public_failed_generation_observation():
    bundle=sample();bundle['evidence']['streams'].append([{'id':'check','kind':'revoke','slot':'root','expected':1,'observed':False}])
    result=transform(bundle)
    assert result['ready'] and result['serialization_count']==3
    bundle['evidence']['streams'][1][0]['expected']=0
    result=transform(bundle)
    assert result['classification']=='inconsistent_evidence' and result['serialization_count']==0 and result['owner_request'] is None
