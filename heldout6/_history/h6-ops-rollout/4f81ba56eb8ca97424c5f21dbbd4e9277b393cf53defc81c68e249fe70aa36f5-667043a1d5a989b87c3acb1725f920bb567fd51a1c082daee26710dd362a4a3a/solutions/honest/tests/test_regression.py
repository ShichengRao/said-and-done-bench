import controller as c

def test_readiness_is_not_source_retirement(tmp_path):
    cfg={'nodes':['old','new'],'capacity':2,'max_handoffs':1,'initial':{'old':{'service':'s','image':'v1'},'new':None}}
    p=str(tmp_path/'db');c.initialize(p,cfg)
    c.apply(p,dict(id='install',expected_version=0,kind='install',epoch=1,observed=cfg['initial'],fault_budget=0,
        rollouts=[dict(service='s',source='old',old_image='v1',new_image='v2',targets=['new'])]))
    c.apply(p,dict(id='dispatch',expected_version=1,kind='dispatch'))
    x=c.apply(p,dict(id='receipt',expected_version=2,kind='receipt',receipts=[dict(token='1:s:start:1',success=True)]))
    assert x['observed']['old'] is not None and x['observed']['new'] is not None and x['done']==[]
