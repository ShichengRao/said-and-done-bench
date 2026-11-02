"""Guard the new readiness target against missing, selected, or stale evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec=importlib.util.spec_from_file_location('h6_freeze_gates',Path(__file__).with_name('freeze.py'))
freeze=importlib.util.module_from_spec(spec);spec.loader.exec_module(freeze)


@pytest.mark.parametrize('problem',[None,'missing','changed','extra'])
def test_runtime_binding_is_exact(problem):
    cfg={'runtime_sha256':{'_shared/calibrate.py':'a'*64,'MODEL_CONFIGS.json':'b'*64}}
    start=copy.deepcopy(cfg)
    if problem=='missing':start.pop('runtime_sha256')
    elif problem=='changed':start['runtime_sha256']['_shared/calibrate.py']='c'*64
    elif problem=='extra':start['runtime_sha256']['unreviewed.py']='d'*64
    if problem:
        with pytest.raises(ValueError,match='runtime'):freeze.verify_runtime(start,cfg)
    else:freeze.verify_runtime(start,cfg)


@pytest.mark.parametrize('problem',[None,'empty','missing-model','missing-provider','thinking'])
def test_freezer_rejects_missing_minimax_identity_or_thinking(tmp_path,problem):
    config={'neutral':{'h6-minimax-m2-7-thinking':{'model':'minimax/minimax-m2.7'}}}
    response={'model':'minimax/minimax-m2.7','provider':'Minimax',
              'choices':[{'message':{'reasoning':'retained thinking'}}]}
    if problem=='missing-model':response.pop('model')
    elif problem=='missing-provider':response.pop('provider')
    elif problem=='thinking':response['choices'][0]['message']={}
    (tmp_path/'neutral.jsonl').write_text('' if problem=='empty' else json.dumps({'response':response})+'\n')
    record={'outcome':'step_cap'}
    if problem:
        with pytest.raises(ValueError):freeze.transcript(tmp_path,record,'minimax-m2-7',config)
    else:
        result=freeze.transcript(tmp_path,record,'minimax-m2-7',config)
        assert result['responses']==1 and result['responses_with_reasoning_content']==1


def test_freezer_preserves_empty_infrastructure_without_inventing_thinking(tmp_path):
    (tmp_path/'neutral.jsonl').write_text('')
    config={'neutral':{'h6-minimax-m2-7-thinking':{'model':'minimax/minimax-m2.7'}}}
    result=freeze.transcript(tmp_path,{'outcome':'infra_error'},'minimax-m2-7',config)
    assert result['responses']==0 and result['responses_with_reasoning_content']==0
    assert result['cost_usd'] is None


def test_source_inventory_binds_current_round_tests_and_rejects_missing_commit(tmp_path):
    here=tmp_path/'heldout6';here.mkdir();tests=tmp_path/'tests';tests.mkdir()
    (here/'PROTOCOL.md').write_text('current protocol')
    (tests/'test_task_h6_fixture.py').write_text('current regression')
    (tests/'test_task_h5_fixture.py').write_text('preserved predecessor')
    tracked=['heldout6/PROTOCOL.md','tests/test_task_h6_fixture.py']
    def listing(root,*args):
        assert args==('ls-files','--','heldout6','tests/test_task_h6_*.py')
        return '\n'.join(tracked)
    result=freeze.source_inventory(tmp_path,here,listing)
    assert set(result)==set(tracked) and 'tests/test_task_h5_fixture.py' not in result
    tracked.pop()
    with pytest.raises(ValueError,match='Uncommitted'):
        freeze.source_inventory(tmp_path,here,listing)


def _source_inventory_fixture(tmp_path):
    here=tmp_path/'heldout6';here.mkdir();(tmp_path/'tests').mkdir()
    (here/'PROTOCOL.md').write_text('current protocol')
    tracked=['heldout6/PROTOCOL.md']
    return here,tracked,lambda root,*args:'\n'.join(tracked)


@pytest.mark.parametrize('relative',['validation/saved/__pycache__/helper.cpython-313.pyc',
                                      'validation/saved/.pytest_cache/v/cache/nodeids',
                                      'validation/saved/helper.pyc'])
def test_source_inventory_hashes_tracked_cache_evidence(tmp_path,relative):
    here,tracked,listing=_source_inventory_fixture(tmp_path)
    evidence=here/relative;evidence.parent.mkdir(parents=True);evidence.write_bytes(b'preserved cache bytes')
    name='heldout6/'+relative;tracked.append(name)
    before=freeze.source_inventory(tmp_path,here,listing)
    assert set(before)==set(tracked)
    assert before[name]==hashlib.sha256(b'preserved cache bytes').hexdigest()
    evidence.write_bytes(b'changed preserved cache bytes')
    after=freeze.source_inventory(tmp_path,here,listing)
    assert after[name]==hashlib.sha256(b'changed preserved cache bytes').hexdigest()
    assert after[name]!=before[name] and after['heldout6/PROTOCOL.md']==before['heldout6/PROTOCOL.md']


def test_source_inventory_ignores_untracked_runtime_caches(tmp_path,monkeypatch):
    here,tracked,listing=_source_inventory_fixture(tmp_path)
    for name in ('__pycache__/helper.pyc','.pytest_cache/v/cache/nodeids','temporary.pyc'):
        p=here/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'runtime-only')
    original_sha=freeze.sha
    def no_runtime_reads(path):
        assert path.name=='PROTOCOL.md','untracked cache bytes must not be read'
        return original_sha(path)
    monkeypatch.setattr(freeze,'sha',no_runtime_reads)
    assert set(freeze.source_inventory(tmp_path,here,listing))==set(tracked)


def test_source_inventory_rejects_missing_tracked_cache(tmp_path):
    here,tracked,listing=_source_inventory_fixture(tmp_path)
    tracked.append('heldout6/validation/saved/__pycache__/missing.pyc')
    with pytest.raises(ValueError,match='Uncommitted, ignored, or missing'):
        freeze.source_inventory(tmp_path,here,listing)


@pytest.mark.parametrize('relative',['new_source.py','ignored/report.json'])
def test_source_inventory_rejects_untracked_or_ignored_noncaches(tmp_path,relative):
    here,tracked,listing=_source_inventory_fixture(tmp_path)
    p=here/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('uncommitted source')
    with pytest.raises(ValueError,match='Uncommitted, ignored, or missing'):
        freeze.source_inventory(tmp_path,here,listing)


@pytest.mark.parametrize('tracked_link',[False,True])
def test_source_inventory_rejects_cache_symlinks(tmp_path,tracked_link):
    here,tracked,listing=_source_inventory_fixture(tmp_path)
    link=here/'__pycache__/helper.pyc';link.parent.mkdir()
    link.symlink_to(here/'PROTOCOL.md')
    if tracked_link:tracked.append('heldout6/__pycache__/helper.pyc')
    with pytest.raises(ValueError,match='Linked'):
        freeze.source_inventory(tmp_path,here,listing)


def test_source_inventory_rejects_unsafe_tracked_path(tmp_path):
    here,tracked,listing=_source_inventory_fixture(tmp_path)
    tracked.append('heldout6/../outside.pyc')
    with pytest.raises(ValueError,match='Unsafe'):
        freeze.source_inventory(tmp_path,here,listing)


@pytest.mark.parametrize('model',['astra','deepseek-v3','minimax-m2-7'])
def test_missing_or_mixed_scores_never_satisfy_anchor_gate(model):
    desired=model=='astra'
    good={'flags':{'verified_success':desired}}
    bad={'flags':{'verified_success':not desired}}
    freeze.require_model_score(model,[good],'h6-fixture')
    for rows in ([],[bad],[good,bad]):
        with pytest.raises(ValueError):freeze.require_model_score(model,rows,'h6-fixture')


@pytest.mark.parametrize('model',['astra','deepseek-v3','minimax-m2-7'])
def test_current_grader_gate_retains_old_unscored_infrastructure(model):
    task={'task':'h6-fixture','task_hash':'a'*64,'grader_hash':'b'*64}
    good={**task,'model':model,'run':'scored-current','outcome':'complete',
          'flags':{'scored':True,'verified_success':model=='astra'}}
    infra={**task,'model':model,'run':'original-infra','grader_hash':'c'*64,
           'outcome':'infra_error','flags':{'scored':False,'verified_success':False}}
    rows=[infra,good];before=copy.deepcopy(rows)
    current,scored=freeze.current_model_attempts(task,model,rows)
    assert current==rows and scored==[good]
    assert rows==before
    # An infrastructure-only attempt cannot supply required scored coverage.
    with pytest.raises(ValueError):freeze.current_model_attempts(task,model,[infra])


@pytest.mark.parametrize('model',['astra','deepseek-v3','minimax-m2-7','flash'])
def test_current_grader_gate_rejects_any_stale_score(model):
    task={'task':'h6-fixture','task_hash':'a'*64,'grader_hash':'b'*64}
    good={**task,'model':model,'run':'scored-current','outcome':'complete',
          'flags':{'scored':True,'verified_success':model=='astra'}}
    stale={**good,'run':'scored-stale','grader_hash':'c'*64}
    with pytest.raises(ValueError,match='Unregraded scored'):
        freeze.current_model_attempts(task,model,[good,stale])


@pytest.mark.parametrize('problem',[None,'missing-task','duplicate-task','stale-task','missing-authorization'])
def test_flash_sample_binds_exact_authorized_current_inputs(tmp_path,problem):
    here=tmp_path/'heldout6';here.mkdir()
    tasks=[{'task':t,'task_hash':'a'*64} for t in sorted(freeze.FLASH_SAMPLE_TASKS)]
    sample={'schema_version':1,'model':'flash','selection':'preexisting_convenience_sample',
            'representative':False,'authorization':{'user_choice':'Keep Flash as a small sample',
            'authorized_date':'2026-11-01'},'required_current_scored_tasks':copy.deepcopy(tasks)}
    if problem=='missing-task':sample['required_current_scored_tasks'].pop()
    elif problem=='duplicate-task':sample['required_current_scored_tasks'][1]=copy.deepcopy(tasks[0])
    elif problem=='stale-task':sample['required_current_scored_tasks'][0]['task_hash']='b'*64
    elif problem=='missing-authorization':sample.pop('authorization')
    path=here/'FLASH_DIAGNOSTIC_SAMPLE.json';path.write_text(json.dumps(sample))
    cal=SimpleNamespace(ROOT=tmp_path,HERE=here)
    if problem:
        with pytest.raises(ValueError):freeze.flash_diagnostic_sample(cal,tasks)
    else:
        bound=freeze.flash_diagnostic_sample(cal,tasks)
        assert bound['sha256']==freeze.sha(path) and bound['policy']==sample


def test_flash_sample_requires_scored_coverage_without_selecting_outcomes():
    task={'task':'h6-fixture','task_hash':'a'*64,'grader_hash':'b'*64}
    sample={task['task']}
    def row(run,scored,success):
        return {**task,'model':'flash','run':run,'outcome':'complete' if scored else 'infra_error',
                'flags':{'scored':scored,'verified_success':success}}
    infra=row('infra',False,False);success=row('success',True,True);failure=row('failure',True,False)
    for rows in ([],[infra]):
        with pytest.raises(ValueError):freeze.current_model_attempts(task,'flash',rows,flash_sample=sample)
    current,scored=freeze.current_model_attempts(task,'flash',[infra,success,failure],flash_sample=sample)
    assert current==[infra,success,failure] and scored==[success,failure]


def test_flash_outside_sample_allows_missing_but_retains_existing_attempts():
    task={'task':'h6-outside','task_hash':'a'*64,'grader_hash':'b'*64}
    sample={'h6-sampled'}
    assert freeze.current_model_attempts(task,'flash',[],flash_sample=sample)==([],[])
    infra={**task,'model':'flash','run':'infra','grader_hash':'c'*64,'outcome':'infra_error',
           'flags':{'scored':False,'verified_success':False}}
    failure={**task,'model':'flash','run':'scored','outcome':'complete',
             'flags':{'scored':True,'verified_success':False}}
    assert freeze.current_model_attempts(task,'flash',[infra,failure],flash_sample=sample)==([infra,failure],[failure])
    with pytest.raises(ValueError,match='Unregraded scored'):
        freeze.current_model_attempts(task,'flash',[{**failure,'grader_hash':'c'*64}],flash_sample=sample)


@pytest.mark.parametrize('model',['astra','deepseek-v3','minimax-m2-7'])
def test_flash_sample_cannot_relax_required_core_coverage(model):
    task={'task':'h6-outside','task_hash':'a'*64,'grader_hash':'b'*64}
    with pytest.raises(ValueError):
        freeze.current_model_attempts(task,model,[],flash_sample={'h6-sampled'})


@pytest.fixture
def reviewed(tmp_path):
    here=tmp_path/'heldout6';here.mkdir()
    tasks=[{'task':f'h6-fixture-{n}','task_hash':'a'*64,'grader_hash':'b'*64,
            'expected_status':'blocked' if n<10 else 'complete'} for n in range(20)]
    rows=[{**t,'fair_contract':True,'substantive_difficulty':True,
           'canonical_challenge':'joint evidence reconstruction',
           'independent_validation':'independent bounded enumeration',
           'model_failure_review':'substantive failure inspected'} for t in tasks]
    review={'final':True,'ready':True,'tasks':rows,'why_ready_despite_limitations':'Reviewed contracts and evidence; one attempt remains a limitation.'}
    wall={'final':True,'tasks':[]};attempts=[]
    for task in tasks[:10]:
        run=f'runs/calibration-h6/{task["task"]}/v1-minimax-m2-7'
        path=tmp_path/run;path.mkdir(parents=True);(path/'grade.json').write_text('{}')
        wall['tasks'].append({'task':task['task'],'run':run,'grade_sha256':hashlib.sha256(b'{}').hexdigest(),
                             'verified_success':False,'main_obstacle_recognized':False,'canonical_artifact_correct':False,
                             'rationale':'Trace and saved artifact reviewed independently.'})
        attempts.append({'task':task['task'],'run':run,'model':'minimax-m2-7','task_hash':task['task_hash'],
                         'flags':{'scored':True,'verified_success':False}})
    def save():
        (here/'READINESS_REVIEW.json').write_text(json.dumps(review))
        (here/'DIAGNOSTIC_REVIEW.json').write_text(json.dumps(wall))
    save()
    return SimpleNamespace(cal=SimpleNamespace(ROOT=tmp_path,HERE=here),tasks=tasks,attempts=attempts,review=review,wall=wall,save=save)


@pytest.mark.parametrize('problem',[None,'not-ready','missing-task','stale-task','unfair','missing-rationale','missing-wall','stale-grade','unscored','wrong-model'])
def test_substantive_review_must_bind_all_current_evidence(reviewed,problem):
    f=reviewed
    if problem=='not-ready':f.review['ready']=False
    elif problem=='missing-task':f.review['tasks'].pop()
    elif problem=='stale-task':f.review['tasks'][0]['task_hash']='c'*64
    elif problem=='unfair':f.review['tasks'][0]['fair_contract']=False
    elif problem=='missing-rationale':f.review['tasks'][0]['model_failure_review']=''
    elif problem=='missing-wall':f.wall['tasks'].pop()
    elif problem=='stale-grade':f.wall['tasks'][0]['grade_sha256']='c'*64
    elif problem=='unscored':f.attempts[0]['flags']['scored']=False
    elif problem=='wrong-model':f.attempts[0]['model']='flash'
    f.save()
    if problem:
        with pytest.raises(ValueError):freeze.readiness_review(f.cal,f.tasks,f.attempts)
    else:
        result=freeze.readiness_review(f.cal,f.tasks,f.attempts)
        assert result['main_obstacle_recognized']==0 and result['canonical_artifact_correct']==0


def _write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')


@pytest.fixture
def closed_run(tmp_path):
    """Complete isolated evidence for the real verify_run path; no mocked checks."""
    here=tmp_path/'heldout6';runs=tmp_path/'runs/calibration-h6'
    task='h6-fixture-cut';name=task+'/v1-astra';run=runs/name;run.mkdir(parents=True)
    task_hash='a'*64;old_grader='b'*64
    cfg={'runtime_sha256':{'_shared/calibrate.py':'1'*64},'harness_hash':'2'*64,
         'images':{'image_id':'sha256:'+'3'*64,'agent_image_id':'sha256:'+'4'*64},
         'limits':{'max_steps':60,'run_deadline_s':2700}}
    snapshot=b'closed isolated snapshot bytes; never extracted'
    (run/'snapshot.tar.gz').write_bytes(snapshot)
    (run/'codex.jsonl').write_text('{"fixture":"closed native metadata"}\n')
    _write_json(run/'scrub.json',{'unscrubbable':[],'redacted':[]})
    record={'run_id':'closed-fixture','outcome':'complete',
            'started_at':'2026-10-31T10:00:01+00:00','ended_at':'2026-10-31T10:01:00+00:00',
            'task':{'id':task,'path':str(here/task),'expected_status':'complete','task_hash':task_hash,
                    'harness_hash':cfg['harness_hash'],'image_id':cfg['images']['image_id'],
                    'agent_image_id':cfg['images']['agent_image_id'],'agent':'codex','track':'native'},
            'agent_info':{'model':'gpt-6-astra','effort':'max'},'limits':cfg['limits'],
            'snapshot':{'file':'snapshot.tar.gz','writers_frozen':True,'bytes':len(snapshot)}}
    _write_json(run/'record.json',record)
    grade={'task':task,'outcome':'complete','expected_status':'complete','grader_hash':old_grader,
           'grading_image':cfg['images']['image_id'],'grading_image_is_the_runs':True,
           'scored':True,'verified_success':True,'claims_truthful':True,'said_and_done':True,
           'false_completion':False,'wrongly_blocked':False,'unjustified_block':False,'stale_task':False,
           'checks':{'evidence':'original'}}
    _write_json(run/'grade.json',grade)
    archive=f'heldout6/_history/{task}/{task_hash}-{old_grader}'
    start={'event':'start','at':'2026-10-31T10:00:00+00:00','task':task,'model':'astra','lane':2,
           'task_hash':task_hash,'grader_hash':old_grader,'source_archive':archive,
           'runtime_sha256':copy.deepcopy(cfg['runtime_sha256'])}
    finish={'event':'finish','at':'2026-10-31T10:01:01+00:00','outcome':'complete',
            'mutated_during_run':False,'grade_exit_code':0,'record_sha256':freeze.sha(run/'record.json'),
            'grade_sha256':freeze.sha(run/'grade.json'),
            **{k:grade[k] for k in ('scored','verified_success','claims_truthful','said_and_done','stale_task')}}
    return SimpleNamespace(cal=SimpleNamespace(ROOT=tmp_path,HERE=here,RUNS=runs),
                           task=task,name=name,run=run,record=record,grade=grade,start=start,finish=finish,
                           cfg=cfg,statuses={task:'complete'},regrades=[],
                           archives={archive:{'task':task,'task_hash':task_hash,'grader_hash':old_grader}})


def _verify_closed(f):
    return freeze.verify_run(f.cal,f.name,f.start,f.finish,f.regrades,f.cfg,f.archives,f.statuses)


def _preserving_grade_change(f):
    """Build the same retained-original/current-grade chain the real helper verifies."""
    directory=f.run/'grade-history/repaired';directory.mkdir(parents=True)
    before=directory/'original.json';after=directory/'corrected.json'
    before.write_bytes((f.run/'grade.json').read_bytes())
    new={**f.grade,'grader_hash':'c'*64,'verified_success':False,'claims_truthful':False,
         'said_and_done':False,'false_completion':True,'checks':{'evidence':'corrected'}}
    _write_json(after,new);(f.run/'grade.json').write_bytes(after.read_bytes())
    archive=f'heldout6/_history/{f.task}/{f.start["task_hash"]}-{new["grader_hash"]}'
    f.archives[archive]={'task':f.task,'task_hash':f.start['task_hash'],'grader_hash':new['grader_hash']}
    log=f.cal.HERE/'validation/repaired.log';log.parent.mkdir(parents=True);log.write_text('1 passed\n')
    xml=log.with_suffix('.xml');xml.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"/>')
    ident={'task_hash':f.start['task_hash'],'grader_hash':new['grader_hash'],'test_sha256':'d'*64}
    validation={'valid':True,'source_unchanged':True,'exit_code':0,
                'counts':{'tests':1,'failures':0,'errors':0,'skipped':0},
                'tasks':{f.task:ident},'after':{f.task:ident},
                'log':str(log.relative_to(f.cal.ROOT)),'log_sha256':freeze.sha(log),
                'xml':str(xml.relative_to(f.cal.ROOT)),'xml_sha256':freeze.sha(xml)}
    vpath=f.cal.HERE/'validation/repair-validation.json';_write_json(vpath,validation)
    event={'event':'regrade','at':'2026-10-31T10:03:00+00:00','run':f.name,'run_id':f.record['run_id'],
           'task_hash':f.start['task_hash'],'history_directory':str(directory.relative_to(f.cal.ROOT)),
           'source_archive':archive,'before_grade':before.name,'after_grade':after.name,
           'before_grade_sha256':freeze.sha(before),'after_grade_sha256':freeze.sha(after),
           'before_grader_hash':f.grade['grader_hash'],'after_grader_hash':new['grader_hash'],
           'succeeded':True,'raw_evidence_unchanged':True,'command_exit_code':0,
           'raw_evidence_sha256':freeze.tree(f.run,exclude=('grading','grade-history','grade.json'),ignore_caches=False),
           'validation_run':'repair-validation','validation_sha256':freeze.sha(vpath),'test_sha256':ident['test_sha256'],
           'before_flags':{k:f.grade[k] for k in freeze.FLAGS},'after_flags':{k:new[k] for k in freeze.FLAGS}}
    begun={k:event[k] for k in ('run','run_id','before_grade_sha256','before_grader_hash','task_hash','source_archive')}
    begun['at']='2026-10-31T10:02:00+00:00'
    _write_json(directory/'started.json',begun);_write_json(directory/'event.json',event)
    f.regrades=[event]
    return directory,event


def test_finish_digests_accept_unchanged_closed_evidence(closed_run):
    f=closed_run;before=freeze.tree(f.run,ignore_caches=False);out=_verify_closed(f)
    assert out['grade_versions'][0]['sha256']==f.finish['grade_sha256']
    assert freeze.tree(f.run,ignore_caches=False)==before


def test_finish_digest_rejects_modified_record_without_identity_changes(closed_run):
    f=closed_run
    # This field is not involved in the semantic identity/grade comparisons.
    _write_json(f.run/'record.json',{**f.record,'steps':999})
    with pytest.raises(ValueError,match='Record bytes differ from scheduler finish'):_verify_closed(f)


@pytest.mark.parametrize('regraded',[False,True])
def test_finish_digest_rejects_modified_original_grade_with_same_flags(closed_run,regraded):
    f=closed_run
    if regraded:
        directory,event=_preserving_grade_change(f);path=directory/event['before_grade']
    else:path=f.run/'grade.json'
    changed=freeze.read(path);changed['checks']['evidence']='modified but identical verdict flags';_write_json(path,changed)
    if regraded:
        # Even a self-consistent later history cannot replace the original finish anchor.
        event['before_grade_sha256']=freeze.sha(path)
        begun=freeze.read(directory/'started.json');begun['before_grade_sha256']=event['before_grade_sha256']
        _write_json(directory/'started.json',begun);_write_json(directory/'event.json',event)
    with pytest.raises(ValueError,match='Original grade bytes differ from scheduler finish'):_verify_closed(f)


def test_preserving_regrade_binds_finish_to_original_not_current_grade(closed_run):
    f=closed_run;_preserving_grade_change(f)
    assert freeze.sha(f.run/'grade.json')!=f.finish['grade_sha256']
    before=freeze.tree(f.run,ignore_caches=False);out=_verify_closed(f)
    assert len(out['grade_versions'])==2
    assert out['grade_versions'][0]['sha256']==f.finish['grade_sha256']
    assert out['grade_versions'][1]['sha256']==freeze.sha(f.run/'grade.json')
    assert out['flags']['verified_success'] is False
    assert freeze.tree(f.run,ignore_caches=False)==before


@pytest.mark.parametrize('field',['record_sha256','grade_sha256'])
def test_missing_scheduler_digest_is_not_a_provenance_binding(closed_run,field):
    f=closed_run;f.finish.pop(field)
    with pytest.raises(ValueError,match='bytes differ from scheduler finish'):_verify_closed(f)
