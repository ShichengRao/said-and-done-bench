import copy,json,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from controller import initialize,apply,inspect

def scenario(seed=0):
    names=['n'+str(seed)+'-'+str(i) for i in range(4)]
    cfg=dict(nodes=[dict(id=n,zone='z'+str(i%2),eligible=True,maintenance=i==0) for i,n in enumerate(names)],min_ready=2,max_total=3,min_zones=1)
    initial={names[0]:'old',names[1]:'old'};plan=[dict(op='start',node=names[2]),dict(op='stop',node=names[0]),dict(op='start',node=names[3]),dict(op='stop',node=names[1])]
    install=dict(id='i'+str(seed),kind='install',expect=0,epoch=1,revision='new',target_nodes=names[2:],observed=initial,plan=plan)
    return cfg,initial,install

def call(path,operation,args):
    c="import json,sys,controller;x=json.loads(sys.argv[1]);print(json.dumps(getattr(controller,x[0])(*x[1:])))"
    p=subprocess.run([sys.executable,'-c',c,json.dumps([operation,str(path),*args])],capture_output=True,text=True,timeout=20)
    assert p.returncode==0,p.stderr
    return json.loads(p.stdout)

@pytest.mark.parametrize('seed',range(8))
def test_receipt_driven_progress_and_replay(tmp_path,seed):
    cfg,initial,install=scenario(seed);original=copy.deepcopy(install);db=tmp_path/'state.sqlite';initialize(db,cfg,initial);r=apply(db,install);assert r==dict(version=1,epoch=1,status='installed',step=0,command=None)
    for step,action in enumerate(install['plan']):
        before=inspect(db);tick=dict(id='t'+str(step),kind='tick',expect=before['version']);r=apply(db,tick);cmd=r['command']
        assert r['status']=='command' and cmd==dict(id=f'1:{step}:1',epoch=1,step=step,attempt=1,op=action['op'],node=action['node'],revision='new' if action['op']=='start' else None)
        assert inspect(db)['nodes']==before['nodes'] and inspect(db)['step']==step
        assert apply(db,tick)==r
        wait=apply(db,dict(id='w'+str(step),kind='tick',expect=r['version']));assert wait['status']=='waiting' and wait['command']==cmd
        ack=dict(id='a'+str(step),kind='observe',epoch=1,command=cmd['id'],success=True);response=apply(db,ack);assert response['status']=='applied' and response['step']==step+1
        assert apply(db,ack)==response
    final=inspect(db);assert final['nodes']=={n:'new' for n in install['target_nodes']} and final['pending'] is None and install==original
    done=apply(db,dict(id='done',kind='tick',expect=final['version']));assert done['status']=='done'

def test_failed_attempt_and_delayed_ack_fencing(tmp_path):
    cfg,initial,install=scenario();db=tmp_path/'state.sqlite';initialize(db,cfg,initial);apply(db,install)
    cmd=apply(db,dict(id='t',kind='tick',expect=1))['command'];apply(db,dict(id='fail',kind='observe',epoch=1,command=cmd['id'],success=False))
    new=apply(db,dict(id='retry',kind='tick',expect=3))['command'];assert new['id']=='1:0:2' and inspect(db)['nodes']==initial
    r=apply(db,dict(id='late',kind='observe',epoch=1,command=cmd['id'],success=True));assert r['status']=='stale' and inspect(db)['pending']==new
    apply(db,dict(id='good',kind='observe',epoch=1,command=new['id'],success=True));assert inspect(db)['step']==1

def test_superseded_epoch_and_restart(tmp_path):
    cfg,initial,install=scenario();db=tmp_path/'state.sqlite';call(db,'initialize',[cfg,initial]);call(db,'apply',[install]);old=call(db,'apply',[dict(id='t',kind='tick',expect=1)])['command']
    updated=dict(install,id='next',expect=2,epoch=2,revision='next');call(db,'apply',[updated]);current=call(db,'apply',[dict(id='newtick',kind='tick',expect=3)])['command']
    response=call(db,'apply',[dict(id='old-receipt',kind='observe',epoch=1,command=old['id'],success=True)])
    assert response['status']=='stale' and call(db,'inspect',[])['pending']==current
    assert call(db,'apply',[install])['version']==1
    call(db,'initialize',[cfg,initial])
    assert call(db,'inspect',[])['epoch']==2

@pytest.mark.parametrize('kind',['payload-conflict','unsafe-plan','wrong-final','stale-version','bad-epoch','initialization'])
def test_rejection_is_atomic_and_id_not_consumed(tmp_path,kind):
    cfg,initial,install=scenario();db=tmp_path/'state.sqlite';initialize(db,cfg,initial)
    if kind=='payload-conflict':
        apply(db,install);bad=dict(install,revision='other');previous=inspect(db)
        with pytest.raises(ValueError):apply(db,bad)
        assert inspect(db)==previous;return
    if kind=='initialization':
        previous=inspect(db)
        with pytest.raises(ValueError):initialize(db,cfg,{})
        assert inspect(db)==previous;return
    bad=copy.deepcopy(install)
    if kind=='unsafe-plan':bad['plan']=[bad['plan'][1],bad['plan'][0],*bad['plan'][2:]]
    elif kind=='wrong-final':bad['target_nodes']=[]
    elif kind=='stale-version':bad['expect']=10
    else:bad['epoch']=2
    previous=inspect(db)
    with pytest.raises(ValueError):apply(db,bad)
    assert inspect(db)==previous
    assert apply(db,install)['status']=='installed'

def test_concurrent_duplicate_tick_and_receipt(tmp_path):
    cfg,initial,install=scenario();db=tmp_path/'state.sqlite';initialize(db,cfg,initial);apply(db,install);tick=dict(id='same',kind='tick',expect=1)
    with ThreadPoolExecutor(max_workers=6) as pool:responses=list(pool.map(lambda _:call(db,'apply',[tick]),range(6)))
    assert all(r==responses[0] for r in responses) and inspect(db)['version']==2
    ack=dict(id='same-ack',kind='observe',epoch=1,command=responses[0]['command']['id'],success=True)
    with ThreadPoolExecutor(max_workers=6) as pool:responses=list(pool.map(lambda _:call(db,'apply',[ack]),range(6)))
    assert all(r==responses[0] for r in responses) and inspect(db)['step']==1 and inspect(db)['version']==3

def test_cli_replays_whole_history(tmp_path):
    db=tmp_path/'cli.sqlite';cmd=[sys.executable,'controller.py','data/rehearsal.json',str(db)]
    a=subprocess.run(cmd,capture_output=True,text=True,timeout=20);b=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
    assert a.returncode==b.returncode==0,(a.stderr,b.stderr)
    assert json.loads(a.stdout)==json.loads(b.stdout)
    assert json.loads(a.stdout)['nodes']=={'n2':'v2','n3':'v2'}


def test_intermediate_zone_loss_is_atomic(tmp_path):
    cfg,initial,install=scenario(93);cfg['min_zones']=2;db=tmp_path/'zones.sqlite';initialize(db,cfg,initial)
    bad=copy.deepcopy(install);bad['plan'][1]['node']=list(initial)[1];bad['plan'][3]['node']=list(initial)[0]
    # Counts and final placement are valid; after the second action only the east zone remains.
    prior=inspect(db)
    with pytest.raises(ValueError):apply(db,bad)
    assert inspect(db)==prior
    assert apply(db,install)['status']=='installed'

@pytest.mark.parametrize('kind',['ineligible','maintenance'])
def test_temporary_forbidden_start_is_atomic(tmp_path,kind):
    cfg,initial,install=scenario(94);cfg['nodes'].append(dict(id='temporary',zone='z0',eligible=kind!='ineligible',maintenance=kind=='maintenance'))
    db=tmp_path/'destination.sqlite';initialize(db,cfg,initial);prior=inspect(db)
    a,b=list(initial);c,d=install['target_nodes'];bad=copy.deepcopy(install)
    bad['plan']=[dict(op='start',node='temporary'),dict(op='stop',node=a),dict(op='start',node=c),dict(op='stop',node='temporary'),dict(op='start',node=d),dict(op='stop',node=b)]
    with pytest.raises(ValueError):apply(db,bad)
    assert inspect(db)==prior
    assert apply(db,install)['status']=='installed'
