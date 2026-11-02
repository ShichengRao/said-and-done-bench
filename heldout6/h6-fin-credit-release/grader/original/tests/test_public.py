from funding import analyze


def example():
    return {'as_of':2,'horizon':2,'obligations':[{'id':'invoice','cents':1,'pay_stage':1,'repay_stage':2}],'commitments':[],'facilities':['bank'],'collateral':['pool'],'routes':[{'id':'offer','revision':1,'known':1,'signed':True,'void':False,'obligation':'invoice','facility':'bank','pledge_cents':1,'windows':[{'from_stage':1,'until_stage':2,'pool':'pool'}]}],'scenarios':[{'id':'case','signals':['open','ready'],'reveal_stage':1,'facilities':{'bank':[1,1]},'collateral':{'pool':[1,1]}}],'proposals':[]}


def test_single_known_scenario():
    r=analyze(example())
    assert r['complete'] and r['requested_cents']==1 and r['frozen_cents']==0 and r['policy_count']==1
    assert r['policy']==[{'stage':1,'history':[['open','',[]],['ready','case',[]]],'assignment':[{'obligation':'invoice','route':'offer'}]}]
    assert r['scenario_audits']['case']['usage']=={'stages':[0,1,2],'facilities':{'bank':[0,1,0]},'collateral':{'pool':[0,1,0]}}
    assert r['owner_review']=={'cost':0,'proposals':[],'policy_count':1,'policy':r['policy']}


def test_capacity_failure_is_a_business_obstacle():
    b=example();b['scenarios'][0]['collateral']['pool'][1]=0
    r=analyze(b)
    assert not r['complete'] and r['policy_count']==0 and r['infeasible_cores']==[['case']] and r['owner_review'] is None


def inspection_example():
    def route(identity,ob,facility,pool,start,inspections=()):
        return dict(id=identity,revision=1,known=1,signed=True,void=False,obligation=ob,facility=facility,pledge_cents=1,windows=[dict(from_stage=start,until_stage=4,pool=pool)],inspection_ids=list(inspections))
    worlds=[]
    for case in ['left','right']:
        worlds.append(dict(id=case,signals=['open','pending','pending','published'],reveal_stage=3,facilities={'A':[1,1,1,int(case=='left')],'B':[1,1,1,int(case=='right')],'C':[1]*4},collateral={'P':[1]*4,'Q':[1]*4,'R':[1]*4}))
    return dict(as_of=2,horizon=4,obligations=[dict(id='probe',cents=1,pay_stage=1,repay_stage=4),dict(id='pay',cents=1,pay_stage=2,repay_stage=4)],commitments=[],facilities=['A','B','C'],collateral=['P','Q','R'],routes=[route('probe-route','probe','C','R',1,['classification']),route('pay-A','pay','A','P',2),route('pay-B','pay','B','Q',2)],scenarios=worlds,inspections=[dict(id='classification',stage=2,results={'left':'A-result','right':'B-result'})],proposals=[])


def test_only_earned_later_inspection_can_inform_payment():
    b=inspection_example();r=analyze(b)
    assert r['policy_count']==1 and r['complete']
    assert [n['assignment'] for n in r['policy']]==[[{'obligation':'probe','route':'probe-route'}],[{'obligation':'pay','route':'pay-A'}],[{'obligation':'pay','route':'pay-B'}]]
    assert [n['history'][-1] for n in r['policy'][1:]]==[['pending','',[['classification','A-result']]],['pending','',[['classification','B-result']]]]
    b['routes'][0]['inspection_ids']=[]
    assert analyze(b)['policy_count']==0
