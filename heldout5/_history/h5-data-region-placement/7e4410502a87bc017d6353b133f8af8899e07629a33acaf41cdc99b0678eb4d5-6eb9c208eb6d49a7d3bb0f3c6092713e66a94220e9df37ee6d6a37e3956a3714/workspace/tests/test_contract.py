from pipeline import transform

def test_one_dataset_uses_distinct_domains():
    data={'catalog':{'at':2,'datasets':[{'id':'d','barrier':2,'regions':['r'],'key':'k','replicas':2,'chunks':[{'id':'c','seq':1,'op':'put','bytes':3}]}]},'topology':[{'id':n,'domain':z,'region':'r','capacity':4,'keys':['k'],'cdc':True} for n,z in [('a','x'),('b','x'),('c','y')]],'reservations':[]}
    result=transform(data)
    assert result['ready'] and result['placement']==[{'dataset':'d','nodes':['a','c']}]
    assert result['dataset_bytes']=={'d':3}
