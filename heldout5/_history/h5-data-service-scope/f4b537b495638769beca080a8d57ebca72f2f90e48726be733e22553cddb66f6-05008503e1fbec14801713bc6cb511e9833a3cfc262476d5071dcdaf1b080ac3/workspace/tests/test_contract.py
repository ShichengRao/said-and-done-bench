from pipeline import transform

def test_single_step_authority():
    credential={'id':'c','parent':None,'selectable':True,'tenant':'t','binding':'b','from':0,'until':None,'revoked_at':None,'capabilities':[['r','read']],'uses':1}
    data={'request':{'tenant':'t','binding':'b','entry':['c'],'steps':[{'resource':'r','operation':'read','at':1}]},'credentials':[credential],'handoffs':[],'proposals':[]}
    result=transform(data)
    assert result['ready'] and result['path']==['c']
    assert result['frontiers']==[{'step':1,'states':[{'credential':'c','uses':{'c':1},'path':['c']}]}]
