from funding import analyze


def example():
    return {'as_of':2,'horizon':2,'obligations':[{'id':'invoice','cents':1,'pay_stage':1,'repay_stage':2}],'commitments':[],'facilities':['bank'],'collateral':['pool'],'routes':[{'id':'offer','revision':1,'known':1,'signed':True,'void':False,'obligation':'invoice','facility':'bank','pledge_cents':1,'windows':[{'from_stage':1,'until_stage':2,'pool':'pool'}]}],'scenarios':[{'id':'case','signals':['open','ready'],'reveal_stage':1,'facilities':{'bank':[1,1]},'collateral':{'pool':[1,1]}}],'proposals':[]}


def test_single_known_scenario():
    r=analyze(example())
    assert r['complete'] and r['requested_cents']==1 and r['frozen_cents']==0 and r['policy_count']==1
    assert r['policy']==[{'stage':1,'history':[['open',''],['ready','case']],'assignment':[{'obligation':'invoice','route':'offer'}]}]
    assert r['scenario_audits']['case']['usage']=={'stages':[0,1,2],'facilities':{'bank':[0,1,0]},'collateral':{'pool':[0,1,0]}}
    assert r['owner_review']=={'cost':0,'proposals':[],'policy_count':1,'policy':r['policy']}


def test_capacity_failure_is_a_business_obstacle():
    b=example();b['scenarios'][0]['collateral']['pool'][1]=0
    r=analyze(b)
    assert not r['complete'] and r['policy_count']==0 and r['infeasible_cores']==[['case']] and r['owner_review'] is None
