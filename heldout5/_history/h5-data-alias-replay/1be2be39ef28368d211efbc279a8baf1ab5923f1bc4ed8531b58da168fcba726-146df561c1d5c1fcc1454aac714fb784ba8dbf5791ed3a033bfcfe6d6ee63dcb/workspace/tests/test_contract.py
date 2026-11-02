from pipeline import transform

def test_empty_replay_preserves_metadata():
    customer={'tenant':'x','id':'c','seats':2,'tier':'a','active':True,'extra':{'a':[1,2]}}
    result=transform({'snapshot':{'as_of':5,'watermarks':{'x':4},'customers':[customer]},'decisions':[],'deliveries':[],'identity':[]})
    assert result=={'customers':[customer],'watermarks':{'x':4},'applied':[],'delivery_duplicates':0,'blocker_codes':[]}
