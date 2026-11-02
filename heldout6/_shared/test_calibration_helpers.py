"""Fixture tests for evidence eligibility, preserved grades, and registry isolation."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def module(name):
    spec = importlib.util.spec_from_file_location('test_h6_' + name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


summary = module('summarize')
cal = summary.calibrate
configured = module('run_configured')


def test_new_round_paths_never_target_frozen_run_directories():
    assert cal.HERE == cal.ROOT/'heldout6'
    assert cal.RUNS == cal.ROOT/'runs/calibration-h6'
    assert summary.HERE == cal.HERE and summary.RUNS == cal.RUNS


@pytest.fixture
def run_fixture(tmp_path, monkeypatch):
    root = tmp_path / 'project'; here = root / 'heldout6'; runs = root / 'runs/calibration-h6'
    task = 'h6-fixture'; run = runs / task / 'v1-flash'; run.mkdir(parents=True)
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
             'scored':True,'verified_success':False,'claims_truthful':False,'said_and_done':False,
             'false_completion':False,'wrongly_blocked':False,'unjustified_block':True}
    events = [{'event':'start','at':'2026-10-30T12:00:00+00:00','task':task,'model':'flash',
               'run':task+'/v1-flash','task_hash':ident['task_hash'],'grader_hash':ident['grader_hash'],'source_archive':'fixture',
               'runtime_sha256':copy.deepcopy(cfg['runtime_sha256'])},
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
    assert set(observed['models'])=={'h6-minimax-m2-7-thinking'}
    assert observed['models']['h6-minimax-m2-7-thinking'].params['reasoning']['enabled'] is True


@pytest.mark.parametrize('problem',[None,'provider','model','thinking','limits','snapshot'])
def test_scheduler_rejects_changed_diagnostic_evidence(run_fixture,problem):
    f=run_fixture
    model=f.cfg['neutral'][cal.CONFIG_NAMES['minimax-m2-7']]
    f.record['agent_info']={**{k:model[k] for k in ['model','base_url','params']},'model_config':model['name']}
    response={'model':model['model'],'provider':'Minimax','choices':[{'message':{'reasoning':'retained thinking'}}]}
    if problem=='provider':response['provider']='another provider'
    elif problem=='model':response['model']='another model'
    elif problem=='thinking':response['choices'][0]['message']={}
    elif problem=='limits':f.record['limits']={**f.cfg['limits'],'max_steps':61}
    elif problem=='snapshot':f.record['snapshot']['writers_frozen']=False
    f.save()
    (f.run/'neutral.jsonl').write_text(json.dumps({'response':response})+'\n')
    issues=cal.existing_grade_issues(f.run,f.identity,'minimax-m2-7',f.cfg)
    assert bool(issues)==bool(problem)


def test_summary_does_not_read_live_response_content(run_fixture,monkeypatch):
    f=run_fixture;f.record['ended_at']=None;f.save()
    def forbidden(_):
        raise AssertionError('Live response content must remain unread')
    monkeypatch.setattr(summary,'response_evidence',forbidden)
    result=inspect(f)
    assert not result['closed'] and not result['score_eligible']


@pytest.mark.parametrize('problem',['empty','missing-model','missing-provider','partial-missing','malformed-envelope','malformed-json','runtime','missing-verified-flag','invalid-verified-flag'])
def test_summary_rejects_absent_partial_or_unbound_evidence(run_fixture,problem):
    f=run_fixture;model=f.record['agent_info']['model']
    rows=[{'response':{'model':model,'provider':'DeepInfra'}}]
    if problem=='empty':rows=[]
    elif problem=='missing-model':rows[0]['response'].pop('model')
    elif problem=='missing-provider':rows[0]['response'].pop('provider')
    elif problem=='partial-missing':rows.append({'response':{'model':model}})
    elif problem=='malformed-envelope':rows.append({'response':[]})
    elif problem=='runtime':f.events[0]['runtime_sha256']={'_shared/calibrate.py':'0'*64}
    elif problem=='missing-verified-flag':f.grade.pop('verified_success')
    elif problem=='invalid-verified-flag':f.grade['verified_success']=0
    (f.run/'neutral.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+('\nnot json' if problem=='malformed-json' else ''))
    f.save();out=inspect(f)
    assert not out['score_eligible'] and out['ineligibility_reasons']


@pytest.mark.parametrize('reasoning',[None,'reasoning','reasoning_content','reasoning_details'])
def test_summary_requires_actual_minimax_thinking_evidence(run_fixture,reasoning):
    f=run_fixture;old=f.run;f.run=old.with_name('v1-minimax-m2-7');old.rename(f.run)
    # The fixture's writer closes over the original Path; write this renamed record explicitly.
    model=f.cfg['neutral'][cal.CONFIG_NAMES['minimax-m2-7']]
    f.record['agent_info']={**{k:model[k] for k in ['model','base_url','params']},'model_config':model['name']}
    for e in f.events:e['run']=f.identity['task']+'/v1-minimax-m2-7';e['model']='minimax-m2-7'
    (f.run/'record.json').write_text(json.dumps(f.record))
    message={} if reasoning is None else {reasoning:'retained thinking'}
    response={'model':model['model'],'provider':'Minimax','choices':[{'message':message}]}
    (f.run/'neutral.jsonl').write_text(json.dumps({'response':response})+'\n')
    out=inspect(f)
    assert out['score_eligible'] is (reasoning is not None)


def test_empty_infrastructure_transcript_is_retained_unscored(run_fixture):
    f=run_fixture;f.record['outcome']='infra_error';f.grade.update(outcome='infra_error',scored=False)
    f.events[-1]['outcome']='infra_error';f.save();(f.run/'neutral.jsonl').write_text('')
    out=inspect(f)
    assert out['score_eligible'] and out['grade_flags']['scored'] is False
    assert out['status_only_correct'] is None


def test_current_input_integrity_failure_blocks_strict_gate_without_erasing_history():
    row={'task':'h6-fixture','task_hash':'a'*64,'validated_current_source':True,
         'models':{'astra':{'scored':1,'verified':1},'deepseek-v3':{'scored':1,'verified':0},
                   'minimax-m2-7':{'scored':1,'verified':0}}}
    invalid={'task':row['task'],'task_hash':row['task_hash'],'run':'current-invalid','score_eligible':False}
    assert summary.calibration_gates(row,[])['strict_calibration_met']
    result=summary.calibration_gates(row,[invalid]);assert not result['strict_calibration_met']
    assert result['current_input_ineligible_attempts']==['current-invalid']
    prior={**invalid,'task_hash':'b'*64,'run':'preserved-prior-version'}
    assert summary.calibration_gates(row,[prior])['strict_calibration_met']
