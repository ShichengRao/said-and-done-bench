import copy
import importlib.util
import itertools
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest
import controller as c

spec=importlib.util.spec_from_file_location('_trusted_rollout_oracle',Path(__file__).with_name('oracle.py'))
o=importlib.util.module_from_spec(spec);spec.loader.exec_module(o)
DATA=json.loads((Path(__file__).parent/'original/data/input.json').read_text())


def ticket_fields(t):return {k:t[k] for k in ('service','source','old_image','new_image','targets')}
def semantic(x):
    result={k:x[k] for k in ('version','epoch','done','quarantine','faults_left','complete')}
    result['observed']={n:None if v is None else {k:v[k] for k in ('service','image')} for n,v in x['observed'].items()}
    result['pending']={t:{k:p[k] for k in ('op','service','source','target','image','attempt')} for t,p in x['pending'].items()}
    result['handoffs']={s:{k:h[k] for k in ('source','target','phase','attempt')} for s,h in x['handoffs'].items()}
    result['rollouts']=None if x['rollouts'] is None else {s:ticket_fields(t) for s,t in x['rollouts'].items()}
    return copy.deepcopy(result)


def call(path,kind,**kw):
    v=c.inspect(path)['version'];return c.apply(path,dict(id='request-'+str(v),expected_version=v,kind=kind,**kw))


def setup(tmp_path,cfg=None,plan=None):
    cfg=copy.deepcopy(DATA['configuration'] if cfg is None else cfg)
    plan=copy.deepcopy(DATA['install'] if plan is None else plan)
    p=str(tmp_path/'controller.db');c.initialize(p,cfg);call(p,'install',**plan);return p


def receipts(p,*pairs):return call(p,'receipt',receipts=[dict(token=t,success=s) for t,s in pairs])


def assert_safe(p,cfg):
    state=semantic(c.inspect(p));present=[v for v in state['observed'].values() if v]
    assert set(v['service'] for v in present)==set(state['rollouts'])
    reserves=[a['target'] for a in state['pending'].values() if a['op']=='start']
    assert len(reserves)==len(set(reserves)) and len(present)+len(reserves)<=cfg['capacity']
    assert all(state['observed'][n] is None for n in reserves+state['quarantine'])
    assert len(state['pending'])<=cfg['max_handoffs'] and len(state['handoffs'])<=cfg['max_handoffs']
    assert o.all_pending_outcomes_win(state,state['handoffs'],cfg)


def test_supplied_trace_receipts_are_atomic_and_bound_to_attempts(tmp_path):
    p=setup(tmp_path);original_dispatch=None
    expected_created={0:['1:B:start:1','1:C:start:1'],2:[],4:['1:B:retire:1'],5:[],
        8:['1:D:start:1'],10:['1:D:retire:1'],12:['1:C:start:2'],15:['1:C:retire:2'],
        17:['1:A:start:1'],19:['1:A:retire:1']}
    for index,request in enumerate(DATA['trace']):
        before=c.inspect(p);argument=copy.deepcopy(request)
        if index in (6,13):
            with pytest.raises(ValueError):c.apply(p,argument)
            assert c.inspect(p)==before
        else:
            result=c.apply(p,argument)
            if index in expected_created:assert result['created']==expected_created[index]
            if index==0:original_dispatch=result
            if index==21:assert result==original_dispatch and c.inspect(p)==before
            if index in (2,3,4,5):assert c.inspect(p)['observed']['b'] is not None
            if index==7:assert result['observed']['b'] is None and result['receipts'][1]['disposition']=='replayed'
            if index==20:assert [r['disposition'] for r in result['receipts']]==['applied','replayed']
            assert_safe(p,DATA['configuration'])
        assert argument==request
    final=semantic(c.inspect(p));assert final['complete'] and final['version']==21
    assert final['done']==list('ABCD') and final['quarantine']==['y'] and final['faults_left']==0
    assert final['observed']=={'a':None,'b':{'service':'D','image':'new'},'c':{'service':'A','image':'new'},
                              'd':{'service':'C','image':'new'},'x':{'service':'B','image':'new'},'y':None}


def test_literal_macro_certificate_and_pending_quantifier():
    plan=DATA['install'];tickets={t['service']:t for t in plan['rollouts']};loc={s:t['source'] for s,t in tickets.items()}
    args=(tickets,loc,set(),set(),DATA['configuration']['nodes'],6)
    paths=o.schedules(*args);robust=o.robust_spines(*args,1)
    assert len(paths)==44 and len(robust)==10
    assert {p[0] for p in robust}=={('B','x'),('C','y')}
    snap=dict(rollouts=tickets,done=[],observed=plan['observed'],quarantine=[],faults_left=1)
    pair={'B':dict(source='b',target='x',phase='starting',attempt=1),'C':dict(source='c',target='y',phase='starting',attempt=1)}
    branches=list(o.projections(snap,pair));assert len(branches)==3
    assert o.all_pending_outcomes_win(snap,pair,DATA['configuration'])
    assert sorted(len(o.schedules(tickets,l,d,b,DATA['configuration']['nodes'],6)) for l,d,b,f in branches)==[1,2,4]


@pytest.mark.parametrize('first_outcomes',[(True,True),(False,True),(True,False)])
def test_each_initial_concurrent_outcome_completes(first_outcomes,tmp_path):
    p=setup(tmp_path);first=call(p,'dispatch')['created']
    receipts(p,*zip(first,first_outcomes))
    for _ in range(20):
        if c.inspect(p)['complete']:break
        pending=call(p,'dispatch')['pending'];assert pending
        receipts(p,*[(t,True) for t in reversed(pending)])
        assert_safe(p,DATA['configuration'])
    assert c.inspect(p)['complete']


def test_unused_fault_allowance_must_cover_a_later_failure(tmp_path):
    p=setup(tmp_path);tokens=call(p,'dispatch')['created'];receipts(p,*[(t,True) for t in tokens])
    tokens=call(p,'dispatch')['created'];receipts(p,*[(t,True) for t in tokens])
    assert call(p,'dispatch')['created']==['1:D:start:1']
    receipts(p,('1:D:start:1',False));assert call(p,'dispatch')['created']==['1:D:start:2']
    assert c.inspect(p)['pending']['1:D:start:2']['target']=='c'
    for _ in range(12):
        if c.inspect(p)['complete']:break
        pending=c.inspect(p)['pending'] or call(p,'dispatch')['pending'];assert pending
        receipts(p,*[(t,True) for t in pending]);assert_safe(p,DATA['configuration'])
    assert c.inspect(p)['complete']


def test_double_failure_and_retirement_failure_reject_whole_batches(tmp_path):
    p=setup(tmp_path);a,b=call(p,'dispatch')['created'];before=c.inspect(p)
    with pytest.raises(ValueError):receipts(p,(a,False),(b,False))
    assert c.inspect(p)==before
    receipts(p,(a,True),(b,True));tokens=call(p,'dispatch')['created'];before=c.inspect(p)
    with pytest.raises(ValueError):receipts(p,(tokens[0],True),(tokens[1],False))
    assert c.inspect(p)==before


def test_install_requires_fully_drained_handoffs_and_resets_quarantine_only_then(tmp_path):
    p=setup(tmp_path);a,b=call(p,'dispatch')['created'];receipts(p,(a,True),(b,False))
    before=c.inspect(p);new=copy.deepcopy(DATA['install']);new['epoch']=2
    assert not before['pending'] and before['handoffs']
    with pytest.raises(ValueError):call(p,'install',**new)
    assert c.inspect(p)==before
    stop=call(p,'dispatch')['created'][0];receipts(p,(stop,True))
    # The old epoch is drained but unfinished; an explicit authoritative fence may replace it.
    after=call(p,'install',**new);assert after['epoch']==2 and after['faults_left']==1 and after['quarantine']==[]
    assert receipts(p,(a,False))['receipts'][0]['disposition']=='stale'


@pytest.mark.parametrize('change',['nominal-only','own-source','source-identity','duplicate-ticket','target-unknown'])
def test_invalid_or_unwinnable_installs_preserve_everything(tmp_path,change):
    p=setup(tmp_path);new=copy.deepcopy(DATA['install']);new['epoch']=2
    if change=='nominal-only':
        for t in new['rollouts']:t['targets']=[{'A':'c','B':'x','C':'y','D':'b'}[t['service']]]
    elif change=='own-source':new['rollouts'][0]['targets']=['a']
    elif change=='source-identity':new['rollouts'][0]['old_image']='different'
    elif change=='duplicate-ticket':new['rollouts'][1]=copy.deepcopy(new['rollouts'][0])
    else:new['rollouts'][0]['targets']=['unknown']
    before=c.inspect(p)
    with pytest.raises(ValueError):call(p,'install',**new)
    assert c.inspect(p)==before


def test_generated_routes_and_small_capacity_match_independent_oracle(tmp_path):
    for index in range(12):
        cfg=copy.deepcopy(DATA['configuration']);plan=copy.deepcopy(DATA['install'])
        cfg['max_handoffs']=1+index%2;cfg['capacity']=4+index%3;plan['fault_budget']=index%2
        if index//3%2:plan['rollouts'][index%4]['targets']=plan['rollouts'][index%4]['targets'][:1]
        tickets={t['service']:t for t in plan['rollouts']};loc={s:t['source'] for s,t in tickets.items()}
        possible=o.winning(tickets,loc,set(),set(),cfg['nodes'],cfg['capacity'],plan['fault_budget'])
        root=tmp_path/str(index);root.mkdir();p=str(root/'db');c.initialize(p,cfg)
        if not possible:
            with pytest.raises(ValueError):call(p,'install',**plan)
            continue
        call(p,'install',**plan)
        for _ in range(20):
            if c.inspect(p)['complete']:break
            pending=call(p,'dispatch')['pending'];assert pending;assert_safe(p,cfg)
            receipts(p,*[(t,True) for t in reversed(pending)])
        assert c.inspect(p)['complete']


def test_request_replay_payload_binding_rejected_id_reuse_and_inputs(tmp_path):
    p=setup(tmp_path);q=dict(id='same',expected_version=1,kind='dispatch');original=copy.deepcopy(q);out=c.apply(p,q)
    call(p,'receipt',receipts=[]);assert c.apply(p,q)==out and q==original
    with pytest.raises(ValueError):c.apply(p,{**q,'expected_version':3})
    bad=dict(id='reusable',expected_version=0,kind='dispatch')
    with pytest.raises(ValueError):c.apply(p,bad)
    bad['expected_version']=c.inspect(p)['version'];assert c.apply(p,bad)['version']==4


def test_thread_cas_and_fresh_process_durability(tmp_path):
    import subprocess,sys
    p=setup(tmp_path)
    def work(i):
        try:return c.apply(p,dict(id='race'+str(i),expected_version=1,kind='dispatch'))
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(work,range(2)))
    assert sum(r is not None for r in results)==1
    assert c.initialize(p,DATA['configuration'])==c.inspect(p)
    script='import controller,json,sys; print(json.dumps(controller.inspect(sys.argv[1])))'
    result=subprocess.run([sys.executable,'-c',script,p],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)==c.inspect(p)


def test_separate_process_cas_and_original_response_survive_restart(tmp_path):
    import subprocess,sys,time
    p=setup(tmp_path);gate=tmp_path/'go'
    script='''import controller,json,sys,time,pathlib
p,ready,gate,identity=sys.argv[1:]
pathlib.Path(ready).touch()
while not pathlib.Path(gate).exists():time.sleep(.005)
q=dict(id=identity,expected_version=1,kind='dispatch')
try: result=controller.apply(p,q)
except ValueError: result=None
print(json.dumps(result))
'''
    children=[subprocess.Popen([sys.executable,'-c',script,p,str(tmp_path/('ready'+str(i))),str(gate),'process'+str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for i in range(2)]
    deadline=time.monotonic()+10
    while not all((tmp_path/('ready'+str(i))).exists() for i in range(2)) and time.monotonic()<deadline:time.sleep(.005)
    gate.touch();outputs=[child.communicate(timeout=15) for child in children]
    assert all(child.returncode==0 for child in children),outputs
    results=[json.loads(out) for out,err in outputs];assert sum(r is not None for r in results)==1
    index=next(i for i,result in enumerate(results) if result is not None)
    call(p,'receipt',receipts=[])
    replay='import controller,json,sys; print(json.dumps(controller.apply(sys.argv[1],dict(id=sys.argv[2],expected_version=1,kind="dispatch"))))'
    child=subprocess.run([sys.executable,'-c',replay,p,'process'+str(index)],capture_output=True,text=True,timeout=15)
    assert child.returncode==0 and json.loads(child.stdout)==results[index]


def test_global_request_replay_survives_a_new_fenced_epoch(tmp_path):
    p=setup(tmp_path)
    original=dict(id='install-again',expected_version=1,kind='install',**{**DATA['install'],'epoch':2})
    response=c.apply(p,original)
    call(p,'install',**{**DATA['install'],'epoch':3});before=c.inspect(p)
    assert c.apply(p,original)==response and c.inspect(p)==before


def diverse_cases():
    families=[
      (['a','b','c','d','x','y'],['A','B','C','D'],[['c','d','x','y'],['a','x'],['d','y'],['b','c','y']],6,2,1),
      (['a','b','c','d','x','y'],['A','B','C','D'],[['c','d','x','y'],['a','x'],['d','y'],['b','c','y']],5,1,1),
      (['a','b','c','d','x','y'],['A','B','C','D'],[['b','c','x','y'],['a','d','x','y'],['a','b','x','y'],['b','c','x','y']],6,2,1),
      (['u','v','w','p','q'],['s','t','r'],[['v','p'],['w','p','q'],['u','p','q']],5,2,1),
      (['u','v','p','q'],['s','t'],[['v','p'],['u','q']],4,2,1),
      (['u','v','w','p'],['s','t','r'],[['p'],['u','p'],['v','p']],4,1,0),
      (['u','p'],['s'],[['p']],2,1,0),
    ]
    for index,(nodes,services,targets,capacity,window,budget) in enumerate(families):
        # Bijective relabeling reverses both service and node lexical priorities in alternating cases.
        nn={n:'node'+str(len(nodes)-i if index%2 else i) for i,n in enumerate(nodes)}
        sn={s:'worker'+str(len(services)-i if index%2 else i) for i,s in enumerate(services)}
        observed={nn[n]:None for n in nodes};tickets=[]
        for source,service,choices in zip(nodes,services,targets):
            observed[nn[source]]={'service':sn[service],'image':'release-'+str(index)}
            tickets.append(dict(service=sn[service],source=nn[source],old_image='release-'+str(index),new_image='next-'+str(index),targets=[nn[n] for n in reversed(choices)]))
        cfg=dict(nodes=list(reversed(list(nn.values()))),capacity=capacity,max_handoffs=window,initial=observed)
        yield cfg,dict(epoch=7,observed=observed,rollouts=list(reversed(tickets)),fault_budget=budget)


def test_diverse_exact_dispatch_matches_literal_oracle(tmp_path):
    for index,(cfg,plan) in enumerate(diverse_cases()):
        tickets={t['service']:t for t in plan['rollouts']};loc={s:t['source'] for s,t in tickets.items()}
        assert o.winning(tickets,loc,set(),set(),cfg['nodes'],cfg['capacity'],plan['fault_budget'])
        root=tmp_path/str(index);root.mkdir();p=setup(root,cfg,plan);attempts={};failed=False
        for turn in range(30):
            before=semantic(c.inspect(p))
            if before['complete']:break
            expected,pending,handoffs=o.dispatch_expectation(before,cfg,attempts)
            actual=call(p,'dispatch');state=semantic(actual)
            assert actual['created']==expected and state['pending']==pending and state['handoffs']==handoffs
            for token in expected:
                command=pending[token]
                if command['op']=='start':attempts[command['service']]=command['attempt']
            assert pending;assert_safe(p,cfg)
            # Deliver ONE receipt at a time to retain genuinely unknown/ready/retiring work.
            token=sorted(pending,reverse=bool(index%2))[0];command=pending[token]
            success=True
            if not failed and plan['fault_budget'] and command['op']=='start' and turn>=index%3:
                success=False;failed=True
            receipts(p,(token,success));assert_safe(p,cfg)
        assert c.inspect(p)['complete']


def test_empty_rollout_installs_completes_and_replays(tmp_path):
    cfg={'nodes':[],'capacity':0,'max_handoffs':2,'initial':{}}
    p=str(tmp_path/'empty.db');assert c.initialize(p,cfg)['complete'] is False
    plan=dict(epoch=1,observed={},rollouts=[],fault_budget=1)
    result=call(p,'install',**plan);assert result['complete'] and result['rollouts']=={}
    request=dict(id='empty-dispatch',expected_version=1,kind='dispatch');out=c.apply(p,request)
    assert out['created']==[] and out['pending']=={} and out['handoffs']=={}
    receipts(p,('1:unknown:start:1',True));before=c.inspect(p)
    assert c.apply(p,request)==out and c.inspect(p)==before
