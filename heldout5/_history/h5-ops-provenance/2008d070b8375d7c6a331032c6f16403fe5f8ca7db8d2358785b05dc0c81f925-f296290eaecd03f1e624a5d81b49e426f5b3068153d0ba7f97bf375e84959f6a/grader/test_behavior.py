import copy,hashlib,json,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
import pytest
from release_gate import initialize,verify_and_stage,inspect
from fixture_support import make,envelope,refresh,targets,canonical

def call(db,name,args):
    code="import json,sys,release_gate;x=json.loads(sys.argv[1]);print(json.dumps(getattr(release_gate,x[0])(*x[1:])))"
    p=subprocess.run([sys.executable,'-c',code,json.dumps([name,str(db),*args])],capture_output=True,text=True,timeout=20)
    assert p.returncode==0,p.stderr
    return json.loads(p.stdout)

@pytest.mark.parametrize('seed',range(8))
def test_signed_rotation_delegated_install_and_restart(tmp_path,seed):
    root,b=make(seed);before=copy.deepcopy(b);db=tmp_path/'trust.sqlite';call(db,'initialize',[root]);out=call(db,'verify_and_stage',[b])
    expected=[dict(path=p,length=len(raw.encode()),sha256=hashlib.sha256(raw.encode()).hexdigest(),role='packages') for p,raw in sorted(b['artifacts'].items())]
    assert out==dict(root_version=2,snapshot_version=5,installed=expected)
    assert call(db,'verify_and_stage',[b])==out
    state=call(db,'inspect',[]);assert state==dict(root_version=2,at=100,snapshot_version=5,roles={'targets':4,'team':4,'packages':4},installed={e['path']:{k:e[k] for k in ['length','sha256']} for e in expected})
    assert b==before

@pytest.mark.parametrize('kind',['old-threshold','new-threshold','root-jump','artifact','pin-length','pin-hash','signature','expired','terminating','cycle'])
def test_invalid_bundle_leaves_anchor_and_cache_unchanged(tmp_path,kind):
    root,b=make(31);db=tmp_path/'trust.sqlite';initialize(db,root);prior=inspect(db)
    if kind=='old-threshold':b['roots'][0]['signatures']=[s for s in b['roots'][0]['signatures'] if s['keyid']!='k0']
    elif kind=='new-threshold':b['roots'][0]['signatures']=[s for s in b['roots'][0]['signatures'] if s['keyid']!='k2']
    elif kind=='root-jump':
        body=dict(b['roots'][0]['signed'],version=3);b['roots'][0]=envelope(body,['k0','k1','k2'])
    elif kind=='artifact':b['artifacts'][b['requested'][-1]]+='changed'
    elif kind in ('pin-length','pin-hash'):
        meta=b['snapshot']['signed']['meta']['packages'];meta['length' if kind=='pin-length' else 'sha256']=1 if kind=='pin-length' else '0'*64;b['snapshot']=envelope(b['snapshot']['signed'],['k2'])
    elif kind=='signature':b['metadata']['packages']['signatures']=[dict(keyid='k2',sig='01')];refresh(b)
    elif kind=='expired':
        b['metadata']['packages']=envelope(dict(b['metadata']['packages']['signed'],expires=100),['k2']);refresh(b)
    elif kind=='terminating':
        b['metadata']['team']=envelope(targets('team',{}),['k1']);top=b['metadata']['targets']['signed'];top['delegations'][0]['terminating']=True;top['delegations'].append(dict(name='packages',paths=['apps/*'],keyids=['k2'],threshold=1,terminating=False));b['metadata']['targets']=envelope(top,['k2']);refresh(b)
    else:
        team=b['metadata']['team']['signed'];team['delegations']=[dict(name='targets',paths=['apps/*'],keyids=['k2'],threshold=1,terminating=False)];b['metadata']['team']=envelope(team,['k1']);refresh(b)
    with pytest.raises(ValueError):verify_and_stage(db,b)
    assert inspect(db)==prior
    # A rejected ID remains usable by the original, valid bundle.
    good=make(31)[1];assert verify_and_stage(db,good)['root_version']==2

@pytest.mark.parametrize('kind',['snapshot-version','snapshot-equivocation','role-version','role-equivocation','time','operation-conflict'])
def test_persistent_rollback_and_equivocation(tmp_path,kind):
    root,b=make(44);db=tmp_path/'trust.sqlite';initialize(db,root);verify_and_stage(db,b);prior=inspect(db);nextb=copy.deepcopy(b);nextb.update(id='next',roots=[],at=101)
    if kind=='operation-conflict':nextb['id']=b['id']
    elif kind=='time':nextb['at']=99
    elif kind=='snapshot-version':nextb['snapshot']['signed']['version']=4;refresh(nextb)
    elif kind=='snapshot-equivocation':nextb['snapshot']['signed']['expires']=179;refresh(nextb)
    else:
        nextb['snapshot']['signed']['version']=6;body=nextb['metadata']['packages']['signed']
        if kind=='role-version':body['version']=3
        else:body['expires']=190
        nextb['metadata']['packages']=envelope(body,['k2']);refresh(nextb)
    with pytest.raises(ValueError):verify_and_stage(db,nextb)
    assert inspect(db)==prior
    assert verify_and_stage(db,b)['snapshot_version']==5

def test_distinct_threshold_and_expired_anchor_without_rotation(tmp_path):
    root,b=make(63);db=tmp_path/'trust.sqlite';initialize(db,root)
    b['roots'][0]['signatures']=[b['roots'][0]['signatures'][0]]*3
    with pytest.raises(ValueError):verify_and_stage(db,b)
    root,b=make(63);b['roots']=[]
    with pytest.raises(ValueError):verify_and_stage(db,b)

def test_concurrent_exact_replay(tmp_path):
    root,b=make(71);db=tmp_path/'trust.sqlite';initialize(db,root)
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(lambda _:call(db,'verify_and_stage',[b]),range(6)))
    assert all(x==results[0] for x in results) and inspect(db)['root_version']==2

def test_later_root_update_and_partial_install_retention(tmp_path):
    root,b=make(88);db=tmp_path/'trust.sqlite';initialize(db,root);verify_and_stage(db,b)
    old=inspect(db);updated=copy.deepcopy(b);updated.update(id='later',at=110)
    r3=dict(b['roots'][0]['signed'],version=3,expires=220)
    updated['roots']=[envelope(r3,['k1','k2'])]
    paths=sorted(b['requested']);updated['artifacts'][paths[0]]+='-updated'
    updated['metadata']['packages']=envelope(targets('packages',updated['artifacts'],version=5),['k2'])
    updated['snapshot']['signed'].update(version=6,expires=210);refresh(updated);updated['requested']=[paths[0]]
    out=verify_and_stage(db,updated);raw=updated['artifacts'][paths[0]]
    info=dict(length=len(raw.encode()),sha256=hashlib.sha256(raw.encode()).hexdigest())
    assert out==dict(root_version=3,snapshot_version=6,installed=[dict(path=paths[0],role='packages',**info)])
    assert inspect(db)==dict(root_version=3,at=110,snapshot_version=6,roles={'targets':4,'team':4,'packages':5},installed={paths[0]:info,paths[1]:old['installed'][paths[1]]})
    again=copy.deepcopy(updated);again.update(id='third',at=115,roots=[],requested=[paths[1]])
    again['snapshot']['signed']['version']=7;refresh(again)
    response=verify_and_stage(db,again)
    assert response==dict(root_version=3,snapshot_version=7,installed=[dict(path=paths[1],role='packages',**old['installed'][paths[1]])])
    assert inspect(db)['installed']=={paths[0]:info,paths[1]:old['installed'][paths[1]]}
    assert verify_and_stage(db,updated)==out

def test_cli_replay(tmp_path):
    db=tmp_path/'cli.sqlite';cmd=[sys.executable,'release_gate.py','data/initial-root.json','data/bundle.json',str(db)]
    a=subprocess.run(cmd,capture_output=True,text=True,timeout=20);b=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
    assert a.returncode==b.returncode==0,(a.stderr,b.stderr)
    assert json.loads(a.stdout)==json.loads(b.stdout) and json.loads(a.stdout)['root_version']==2


def test_nested_termination_propagates_across_nonterminating_parent(tmp_path):
    root,b=make(96);db=tmp_path/'nested.sqlite';initialize(db,root);prior=inspect(db)
    top=b['metadata']['targets']['signed'];top['delegations'].append(dict(name='packages',paths=['apps/*'],keyids=['k2'],threshold=1,terminating=False))
    b['metadata']['targets']=envelope(top,['k2'])
    b['metadata']['team']=envelope(targets('team',{},[dict(name='empty',paths=['apps/*'],keyids=['k2'],threshold=1,terminating=True)]),['k1'])
    b['metadata']['empty']=envelope(targets('empty',{}),['k2']);refresh(b)
    # The direct parent is nonterminating. The child must still stop root-level fallback.
    with pytest.raises(ValueError):verify_and_stage(db,b)
    assert inspect(db)==prior
    # Removing only the descendant's termination permits the same fallback and ID.
    team=b['metadata']['team']['signed'];team['delegations'][0]['terminating']=False;b['metadata']['team']=envelope(team,['k1']);refresh(b)
    out=verify_and_stage(db,b)
    assert [entry['path'] for entry in out['installed']]==sorted(b['requested'])
    assert all(entry['role']=='packages' for entry in out['installed'])
