"""Fixture tests for evidence eligibility, preserved grades, and registry isolation."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def module(name):
    spec = importlib.util.spec_from_file_location('test_h5_' + name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


summary = module('summarize')
cal = summary.calibrate
configured = module('run_configured')
queued = module('queue_diagnostic')
recovery = module('recover_v3')
parallel = module('parallel_diagnostic')


@pytest.fixture
def run_fixture(tmp_path, monkeypatch):
    root = tmp_path / 'project'; here = root / 'heldout5'; runs = root / 'runs/calibration-h5'
    task = 'h5-fixture'; run = runs / task / 'v1-flash'; run.mkdir(parents=True)
    cfg = copy.deepcopy(cal.verify_configs()); model = cfg['neutral'][cal.CONFIG_NAMES['flash']]
    ident = {'task': task, 'task_hash': 'a'*64, 'grader_hash': 'b'*64,
             'expected_status': 'blocked', 'validated_current_source': True}
    record = {'run_id': 'fixture', 'outcome': 'blocked', 'submit': {'status': 'blocked'},
              'started_at': '2026-10-30T12:00:01+00:00', 'ended_at': '2026-10-30T12:01:00+00:00',
              'task': {'id': task, 'path': str(here/task), 'task_hash': ident['task_hash'],
                       'expected_status': 'blocked', 'harness_hash': cfg['harness_hash'],
                       'image': cfg['images']['image'], 'image_id': cfg['images']['image_id'],
                       'agent_image': cfg['images']['image'], 'agent_image_id': cfg['images']['image_id'],
                       'agent': 'neutral', 'track': 'neutral'},
              'agent_info': {**{k:model[k] for k in ['model','base_url','params']}, 'model_config': model['name']},
              'limits': cfg['limits'], 'snapshot': {'file':'snapshot.tar.gz','bytes':8,'writers_frozen':True},
              'usage_total': {'cost': .123}}
    grade = {'task':task,'outcome':'blocked','expected_status':'blocked','grader_hash':ident['grader_hash'],
             'stale_task':False,'grading_image_is_the_runs':True,'grading_image':cfg['images']['image_id'],
             'scored':True,'verified_success':False,'claims_truthful':False,'said_and_done':False}
    events = [{'event':'start','at':'2026-10-30T12:00:00+00:00','task':task,'model':'flash',
               'run':task+'/v1-flash','task_hash':ident['task_hash'],'grader_hash':ident['grader_hash'],'source_archive':'fixture'},
              {'event':'finish','at':'2026-10-30T12:01:01+00:00','run':task+'/v1-flash','model':'flash',
               'outcome':'blocked','mutated_during_run':False}]
    def save():
        for name,value in [('record.json',record),('grade.json',grade)]:
            (run/name).write_text(json.dumps(value))
    save(); (run/'snapshot.tar.gz').write_bytes(b'snapshot')
    (run/'neutral.jsonl').write_text(json.dumps({'response':{'model':model['model'],'provider':'DeepInfra','usage':{}}})+'\n')
    for name,value in [('ROOT',root),('HERE',here),('RUNS',runs)]:monkeypatch.setattr(summary,name,value)
    monkeypatch.setattr(summary,'archive_errors',lambda *args:[])
    return SimpleNamespace(run=run,cfg=cfg,identity=ident,record=record,grade=grade,events=events,save=save)


def inspect(f):
    return summary.inspect_attempt(f.run,f.identity,f.cfg,f.events,[])


def test_status_only_is_not_verified_and_partial_cost_is_visible(run_fixture):
    f=run_fixture; r=inspect(f)
    assert r['score_eligible'] and r['status_only_correct'] is True
    assert r['grade_flags']['verified_success'] is False
    assert r['cost_usd']==.123 and r['response_cost_coverage']['cost_missing']==1
    assert 'logged responses lack returned cost' in r['cost_caveats']


@pytest.mark.parametrize('problem',['open','stale','image','unvalidated','model','provider','missing-finish','changed-source'])
def test_invalid_evidence_is_retained_but_ineligible(run_fixture,problem):
    f=run_fixture
    if problem=='open':f.record['ended_at']=None
    elif problem=='stale':f.grade['stale_task']=True
    elif problem=='image':f.grade['grading_image']='another-image'
    elif problem=='unvalidated':f.identity['validated_current_source']=False
    elif problem=='model':f.record['agent_info']['model']='another-model'
    elif problem=='provider':
        (f.run/'neutral.jsonl').write_text(json.dumps({'response':{'model':f.record['agent_info']['model'],'provider':'Wrong','usage':{}}})+'\n')
    elif problem=='missing-finish':f.events.pop()
    else:f.events[-1]['mutated_during_run']=True
    f.save();r=inspect(f)
    assert not r['score_eligible'] and r['ineligibility_reasons']
    assert r['run'] and r['cost_usd']==.123


def test_existing_grade_guard_never_mutates_evidence(run_fixture):
    f=run_fixture;before={p.name:p.read_bytes() for p in f.run.iterdir()}
    assert cal.existing_grade_issues(f.run,f.identity,'flash',f.cfg)==[]
    f.identity['grader_hash']='c'*64
    assert 'grade uses another grader' in cal.existing_grade_issues(f.run,f.identity,'flash',f.cfg)
    assert before=={p.name:p.read_bytes() for p in f.run.iterdir()}


def test_infrastructure_snapshot_is_retained_but_never_scored(run_fixture):
    f=run_fixture;f.record['outcome']='infra_error';f.record['snapshot']['writers_frozen']=False
    f.grade.update(outcome='infra_error',scored=False);f.events[-1]['outcome']='infra_error';f.save()
    r=inspect(f)
    assert r['score_eligible'] and r['infrastructure_unfrozen_snapshot']
    assert r['grade_flags']['scored'] is False and r['status_only_correct'] is None
    f.grade['scored']=True;f.save()
    assert not inspect(f)['score_eligible']


def test_registry_bootstrap_only_changes_default_registry(monkeypatch):
    from beambench import neutral
    original=neutral.load_models.__defaults__
    monkeypatch.setattr(neutral.load_models,'__defaults__',original)
    monkeypatch.setattr(configured.sys,'argv',['bootstrap','run','--agent','neutral'])
    observed={}
    def dispatch(name,run_name):
        observed.update(name=name,run_name=run_name,argv=list(configured.sys.argv),models=neutral.load_models())
    monkeypatch.setattr(configured.runpy,'run_module',dispatch)
    configured.main()
    assert observed['name']=='beambench' and observed['run_name']=='__main__'
    assert observed['argv']==['beambench','run','--agent','neutral']
    assert set(observed['models'])=={'h5-minimax-m2-7-thinking'}
    assert observed['models']['h5-minimax-m2-7-thinking'].params['reasoning']['enabled'] is True


@pytest.mark.parametrize('run_name',['h5-data-service-scope/v1-deepseek-v3','h5-fin-credit-release/v1-deepseek-v3'])
@pytest.mark.parametrize('problem',[None,'scored','wrong-error','changed-record','changed-input'])
def test_reviewed_recovery_requires_exact_unscored_provider_failure(tmp_path,monkeypatch,problem,run_name):
    run=tmp_path/run_name;run.mkdir(parents=True)
    record={'outcome':'infra_error','outcome_detail':'HTTP 400: invalid escaped character',
            'task':{'task_hash':'a'*64}}
    grade={'scored':False,'verified_success':False,'grader_hash':'b'*64}
    if problem=='scored':grade['scored']=True
    if problem=='wrong-error':record['outcome_detail']='authentication failed'
    for name,value in [('record.json',record),('grade.json',grade)]:
        (run/name).write_text(json.dumps(value))
    document={'run':run_name,'record_sha256':cal.sha(run/'record.json'),
              'grade_sha256':cal.sha(run/'grade.json'),'task_hash':'a'*64,'grader_hash':'b'*64,
              'planned_retry_revision':'infra-retry-1','reason':'Reviewed provider error'}
    identity={'task_hash':'a'*64,'grader_hash':'b'*64}
    if problem=='changed-record':document['record_sha256']='c'*64
    if problem=='changed-input':identity['task_hash']='c'*64
    monkeypatch.setattr(recovery.cal,'RUNS',tmp_path)
    monkeypatch.setattr(recovery.cal,'validated_identity',lambda task:identity)
    if problem:
        with pytest.raises(AssertionError):recovery.review_failure(document)
    else:assert recovery.review_failure(document)==identity


@pytest.mark.parametrize('state',['ready','incomplete','already-attempted'])
def test_queued_diagnostic_is_gated_without_inference(tmp_path,monkeypatch,state):
    runs=tmp_path/'runs';(runs/'control').mkdir(parents=True);(runs/'control/scheduler.lock').write_text('')
    monkeypatch.setattr(queued.calibrate,'RUNS',runs)
    tasks=[{'task':f'h5-fixture-{i}'} for i in range(20)]
    monkeypatch.setattr(queued.summarize,'collect',lambda:{'strict_calibration_tasks':19 if state=='incomplete' else 20,'tasks':tasks})
    calls=[]
    monkeypatch.setattr(queued.subprocess,'call',lambda command,**kw:calls.append(command) or 0)
    if state=='already-attempted':(runs/'h5-fixture-0/v1-minimax-m2-7').mkdir(parents=True)
    if state=='ready':
        assert queued.main()==0 and len(calls)==1
        assert calls[0][-5:]==['--revision','v1','--models','minimax-m2-7','--diagnostic-lane']
        assert all(task['task'] in calls[0] for task in tasks)
    else:
        with pytest.raises(SystemExit):queued.main()
        assert not calls


@pytest.mark.parametrize('problem',[None,'unfinished','provider-stop'])
def test_parallel_transition_keeps_completed_attempts(tmp_path,monkeypatch,problem):
    here=tmp_path/'heldout5';here.mkdir();runs=tmp_path/'runs';control=runs/'control';control.mkdir(parents=True)
    for name in ('scheduler.lock','diagnostic.lock'):(control/name).write_text('')
    (control/'STOP_minimax-m2-7').write_text(json.dumps({'reason':'Provider failure' if problem=='provider-stop' else 'Planned scheduler transition'}))
    (here/'ROUND4_BASELINE.json').write_text(json.dumps({'mapping':[{'replacement':x} for x in ('h5-done','h5-new')]}))
    (here/'ADDITIONAL_MODEL_CONFIGS.json').write_text(json.dumps({'additional_diagnostic_lane':{'model':'minimax-m2-7','max_concurrent':1},'combined_neutral_concurrency':2}))
    done=runs/'h5-done/v1-minimax-m2-7';done.mkdir(parents=True);(done/'retained').write_text('original evidence')
    for task in ('h5-done','h5-new'):
        path=runs/task/'v1-astra';path.mkdir(parents=True);(path/'grade.json').write_text('{}')
    for name,value in [('HERE',here),('RUNS',runs),('ROOT',tmp_path)]:monkeypatch.setattr(parallel.cal,name,value)
    monkeypatch.setattr(parallel.cal,'verify_configs',lambda:{})
    monkeypatch.setattr(parallel.cal,'verify_baseline',lambda:None)
    monkeypatch.setattr(parallel.cal,'validated_identity',lambda task:{'task':task})
    monkeypatch.setattr(parallel.cal,'existing_grade_issues',lambda *args:['open'] if problem=='unfinished' else [])
    calls=[];monkeypatch.setattr(parallel.subprocess,'call',lambda command,**kw:calls.append(command) or 0)
    if problem:
        with pytest.raises(AssertionError):parallel.main()
        assert not calls
    else:
        parallel.main();assert len(calls)==1
        assert 'h5-new' in calls[0] and 'h5-done' not in calls[0]
        assert calls[0][-2:]==['--diagnostic-concurrency','3']
        assert not (control/'STOP_minimax-m2-7').exists()
        assert len(list(control.glob('parallel-transition-*/original-stop.json')))==1
    assert (done/'retained').read_text()=='original evidence'
