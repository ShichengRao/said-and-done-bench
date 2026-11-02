"""Temporary-fixture tests only: never invoke Docker, inference, or real run grading."""
import copy
import fcntl
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('h6_regrade_tests_subject', Path(__file__).with_name('regrade.py'))
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    cal = subject.calibrate
    root = tmp_path / 'project'
    here = root / 'heldout6'
    runs = root / 'runs/calibration-h6'
    task_id = 'h6-test-one'
    name = task_id + '/v1-flash'
    task = here / task_id
    (task / 'grader').mkdir(parents=True)
    (task / 'workspace').mkdir()
    (task / 'task.toml').write_text('id="h6-test-one"\nfamily="heldout6-trap"\nexpected_status="complete"\ntracks=["neutral"]\n')
    (task / 'goal.md').write_text('A fixture task.\n')
    (task / 'workspace/code.py').write_text('pass\n')
    (task / 'grader/grade.py').write_text('print("old fixture grader")\n')
    test_file = root / 'tests/test_task_h6_test_one.py'
    test_file.parent.mkdir()
    test_file.write_text('def test_fixture(): pass\n')
    for key, value in {'ROOT': root, 'HERE': here, 'RUNS': runs, 'PYTHON': '/fixture/python'}.items():
        monkeypatch.setattr(cal, key, value)
    monkeypatch.setattr(cal, 'verify_baseline', lambda: None)
    monkeypatch.setattr(cal, 'harness_hash', lambda: 'a' * 64)
    task_spec = cal.load_task(task)
    old_hash = cal.grader_hash(task_spec)
    task_hash = cal.task_hash(task_spec)
    # A grader-only repair changes the grader hash, never the task input hash.
    (task / 'grader/grade.py').write_text('print("new fixture grader")\n')
    identity = {'task_hash': task_hash, 'grader_hash': cal.grader_hash(task_spec),
                'test_file': str(test_file.relative_to(root)), 'test_sha256': subject.sha(test_file)}
    log = here / 'validation/check.log'
    log.parent.mkdir()
    log.write_text('1 passed\n')
    xml = log.with_suffix('.xml')
    xml.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"/>')
    validation = {'run_id': 'fixture-validation', 'valid': True, 'source_unchanged': True,
                  'exit_code': 0, 'counts': {'tests': 1, 'failures': 0, 'errors': 0, 'skipped': 0},
                  'tasks': {task_id: identity}, 'after': {task_id: identity},
                  'log': str(log.relative_to(root)), 'log_sha256': subject.sha(log),
                  'xml': str(xml.relative_to(root)), 'xml_sha256': subject.sha(xml)}
    validation_path = here / 'validation' / f'{task_id}.json'
    write(validation_path, validation)
    write(here/'validation'/('fixture-validation.json'),validation)
    run = runs / name
    record = {'run_id': 'fixture-run', 'outcome': 'complete', 'snapshot':{'writers_frozen':True},
              'started_at': '2026-10-30T10:00:01+00:00', 'ended_at': '2026-10-30T10:01:00+00:00',
              'task': {'id': task_id, 'path': str(task), 'task_hash': task_hash,
                       'harness_hash': 'a' * 64, 'expected_status': 'complete'}}
    write(run / 'record.json', record)
    (run / 'snapshot.tar.gz').write_bytes(b'isolated snapshot fixture; never extracted')
    (run / 'neutral.jsonl').write_text('{"event":"fixture"}\n')
    old = {'task': task_id, 'outcome': 'complete', 'expected_status': 'complete',
           'grader_hash': old_hash, 'stale_task': False, 'scored': True,
           'verified_success': True, 'said_and_done': True, 'claims_truthful': True,
           'grading_image_is_the_runs': True, 'checks': {}}
    write(run / 'grade.json', old)
    history = [
        {'event': 'start', 'at': '2026-10-30T10:00:00+00:00', 'revision': 'v1', 'run': name,
         'task_hash': task_hash, 'grader_hash': old_hash, 'model':'flash'},
        {'event': 'finish', 'at': '2026-10-30T10:01:01+00:00', 'revision': 'v1', 'run': name,
         'outcome': 'complete', 'mutated_during_run': False, 'record_sha256':subject.sha(run/'record.json'), 'grade_sha256':subject.sha(run/'grade.json')},
        {'event': 'scheduler_finished', 'at': '2026-10-30T10:01:02+00:00', 'revision': 'v1'},
    ]
    event_path = runs / 'control/events.jsonl'
    event_path.parent.mkdir()
    event_path.write_text(''.join(json.dumps(e) + '\n' for e in history))
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        kwargs['stdout'].write(b'fixture grade command\n')
        new = dict(old, grader_hash=identity['grader_hash'], verified_success=False, said_and_done=False)
        write(run / 'grade.json', new)
        return SimpleNamespace(returncode=0)

    return SimpleNamespace(cal=cal, root=root, task=task, task_id=task_id, run=run, name=name,
                           old=old, identity=identity, validation=validation,
                           validation_path=validation_path, event_path=event_path, history=history,
                           runner=runner, calls=calls)


def invoke(f, **kwargs):
    return subject.regrade([f.name], 'Add documented CLI coverage; no input changes.', cal=f.cal,
                           runner=kwargs.get('runner', f.runner))


def test_regrade_archives_both_grades_source_and_exact_event(fixture):
    f = fixture
    old_bytes = (f.run / 'grade.json').read_bytes()
    raw = subject.evidence(f.run)
    result = invoke(f)[0]
    directory = f.root / result['history_directory']
    assert (directory / result['before_grade']).read_bytes() == old_bytes
    assert subject.sha(directory / result['before_grade']) == result['before_grade_sha256']
    assert (directory / result['after_grade']).read_bytes() == (f.run / 'grade.json').read_bytes()
    assert subject.read(directory / 'event.json') == subject.events(f.event_path)[-1] == result
    assert result['before_flags']['verified_success'] is True
    assert result['after_flags']['verified_success'] is False
    assert result['reason'] == 'Add documented CLI coverage; no input changes.'
    assert result['command'] == ['/fixture/python', '-m', 'beambench', 'grade', str(f.run)]
    assert result['succeeded'] and result['raw_evidence_unchanged']
    assert subject.evidence(f.run) == raw
    archived = f.cal.load_task(f.root / result['source_archive'])
    assert f.cal.grader_hash(archived) == f.identity['grader_hash']
    assert f.cal.task_hash(archived) == f.identity['task_hash']


def test_repeated_regrade_never_overwrites_prior_grade_versions(fixture):
    f = fixture
    first = invoke(f)[0]
    first_files = {p.name: p.read_bytes() for p in (f.root / first['history_directory']).iterdir()}
    second = invoke(f)[0]
    assert first['history_directory'] != second['history_directory']
    assert {p.name: p.read_bytes() for p in (f.root / first['history_directory']).iterdir()} == first_files
    assert len([e for e in subject.events(f.event_path) if e['event'] == 'regrade']) == 2


@pytest.mark.parametrize('problem', ['missing-grade', 'missing-snapshot', 'not-ended', 'open-outcome',
                                     'different-input', 'invalid-validation', 'failed-validation',
                                     'modified-validation-log', 'no-finish', 'no-scheduler-finish',
                                     'unrecorded-grade', 'mutated-inference'])
def test_guards_abort_before_command_or_history(fixture, problem):
    f = fixture
    if problem == 'missing-grade': (f.run / 'grade.json').unlink()
    elif problem == 'missing-snapshot': (f.run / 'snapshot.tar.gz').unlink()
    elif problem in {'not-ended', 'open-outcome', 'different-input'}:
        record = subject.read(f.run / 'record.json')
        if problem == 'not-ended': record['ended_at'] = ''
        elif problem == 'open-outcome': record['outcome'] = 'running'
        else: record['task']['task_hash'] = '0' * 64
        write(f.run / 'record.json', record)
    elif problem in {'invalid-validation', 'failed-validation'}:
        validation = copy.deepcopy(f.validation)
        if problem == 'invalid-validation': validation['valid'] = False
        else: validation['counts']['failures'] = 1
        write(f.validation_path, validation)
    elif problem == 'modified-validation-log': (f.root / f.validation['log']).write_text('changed')
    elif problem in {'no-finish', 'no-scheduler-finish', 'mutated-inference'}:
        history = copy.deepcopy(f.history)
        if problem == 'mutated-inference': history[1]['mutated_during_run'] = True
        else: history = [e for e in history if e['event'] != ('finish' if problem == 'no-finish' else 'scheduler_finished')]
        f.event_path.write_text(''.join(json.dumps(e) + '\n' for e in history))
    elif problem == 'unrecorded-grade': write(f.run / 'grade.json', dict(f.old, grader_hash='9' * 64))
    with pytest.raises((ValueError, AssertionError)):
        invoke(f)
    assert not f.calls and not (f.run / 'grade-history').exists()


def test_live_scheduler_lock_prevents_regrading(fixture):
    f = fixture
    with (f.event_path.parent / 'scheduler.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match='scheduler is active'):
            invoke(f)
    assert not f.calls


def test_batch_preflight_and_explicit_name_guards(fixture):
    f = fixture
    for names in [[f.name, f.name], ['../outside'], [f.name, 'h6-test-missing/v1-flash']]:
        with pytest.raises((ValueError, AssertionError)):
            subject.regrade(names, 'Reason', cal=f.cal, runner=f.runner)
    with pytest.raises(ValueError, match='reason'):
        subject.regrade([f.name], '  ', cal=f.cal, runner=f.runner)
    assert not f.calls and not (f.run / 'grade-history').exists()


@pytest.mark.parametrize('problem', ['command-error', 'wrong-grader', 'raw-mutated', 'grader-error'])
def test_failed_regrade_preserves_output_and_records_failure(fixture, problem):
    f = fixture
    old_bytes = (f.run / 'grade.json').read_bytes()
    def runner(command, **kwargs):
        f.runner(command, **kwargs)
        if problem == 'wrong-grader':
            new = subject.read(f.run / 'grade.json'); new['grader_hash'] = 'f' * 64
            write(f.run / 'grade.json', new)
        if problem == 'grader-error':
            new = subject.read(f.run / 'grade.json'); new['checks'] = {'grader_error': 'fixture failure'};new['scored'] = False
            write(f.run / 'grade.json', new)
        if problem == 'raw-mutated': (f.run / 'snapshot.tar.gz').write_bytes(b'changed')
        return SimpleNamespace(returncode=1 if problem == 'command-error' else 0)
    with pytest.raises(ValueError, match='evidence retained'):
        invoke(f, runner=runner)
    event = subject.events(f.event_path)[-1]
    directory = f.root / event['history_directory']
    assert event['event'] == 'regrade' and not event['succeeded']
    assert (directory / event['before_grade']).read_bytes() == old_bytes
    assert (directory / event['after_grade']).read_bytes() == (f.run / 'grade.json').read_bytes()
    assert event['raw_evidence_unchanged'] is (problem != 'raw-mutated')


def test_closed_infrastructure_outcome_remains_unscored(fixture):
    f = fixture
    record = subject.read(f.run / 'record.json');record['outcome'] = 'infra_error'
    write(f.run / 'record.json', record)
    f.old.update(outcome='infra_error',scored=False,verified_success=False,said_and_done=False)
    write(f.run / 'grade.json',f.old)
    history = copy.deepcopy(f.history);history[1]['outcome'] = 'infra_error';history[1]['record_sha256']=subject.sha(f.run/'record.json');history[1]['grade_sha256']=subject.sha(f.run/'grade.json')
    f.event_path.write_text(''.join(json.dumps(e)+'\n' for e in history))
    event=invoke(f)[0]
    assert event['succeeded'] and event['after_flags']['outcome']=='infra_error'
    assert event['after_flags']['scored'] is False and event['after_flags']['verified_success'] is False


def test_non_json_grade_failure_is_archived_without_repair(fixture):
    f=fixture
    def runner(command, **kwargs):
        f.calls.append(command);(f.run/'grade.json').write_text('invalid JSON from fixture')
        return SimpleNamespace(returncode=0)
    with pytest.raises(ValueError,match='evidence retained'):
        invoke(f,runner=runner)
    event=subject.events(f.event_path)[-1]
    assert not event['succeeded'] and event['after_grader_hash'] is None
    assert (f.root/event['history_directory']/event['after_grade']).read_text()=='invalid JSON from fixture'
    assert (f.run/'grade.json').read_text()=='invalid JSON from fixture'


def append(f, event):
    subject.append_event(f.event_path, {'at':'2026-10-30T10:02:00+00:00',**event})


def diagnostic(f, name='h6-test-unrelated/v2-minimax-m2-7'):
    append(f,{'event':'start','run':name,'revision':'v2','model':'minimax-m2-7'})


def test_default_diagnostic_lock_is_exclusive(fixture):
    f=fixture
    with (f.event_path.parent/'diagnostic.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(ValueError,match='diagnostic scheduler is active'):invoke(f)
    assert not f.calls and not (f.run/'grade-history').exists()


def test_opt_in_disjoint_live_diagnostic_keeps_running(fixture):
    f=fixture;diagnostic(f)
    with (f.event_path.parent/'diagnostic.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        event=subject.regrade([f.name],'Fair conftest handling.',cal=f.cal,runner=f.runner,
            allow_unrelated_diagnostic=True,diagnostic_tasks=['h6-test-unrelated'])[0]
        # Regrade did not release or replace the unrelated scheduler's lock.
        with (f.event_path.parent/'diagnostic.lock').open('a') as probe:
            with pytest.raises(BlockingIOError):fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert event['succeeded'] and event['raw_evidence_unchanged']
    assert event['diagnostic_policy']['declared_tasks']==['h6-test-unrelated']
    assert event['diagnostic_policy']['diagnostic_lock_held_at_start'] is False
    assert len([e for e in subject.events(f.event_path) if e['event']=='start'])==2


@pytest.mark.parametrize('mode',['undeclared-live','overlapping-declaration','missing-declaration','live-target','closed-record-without-finish'])
def test_disjoint_declaration_and_live_target_guards(fixture,mode):
    f=fixture;declared=['h6-test-unrelated']
    if mode=='undeclared-live':diagnostic(f,'h6-other-unlisted/v2-minimax-m2-7')
    elif mode=='overlapping-declaration':declared.append(f.task_id)
    elif mode=='missing-declaration':declared=[]
    elif mode=='live-target':diagnostic(f,f.task_id+'/v2-minimax-m2-7')
    else:
        f.event_path.write_text(''.join(json.dumps(e)+'\n' for e in f.history if e['event']!='finish'))
    with (f.event_path.parent/'diagnostic.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(ValueError):subject.regrade([f.name],'Fairness repair.',cal=f.cal,runner=f.runner,
            allow_unrelated_diagnostic=True,diagnostic_tasks=declared)
    assert not f.calls and not (f.run/'grade-history').exists()


def test_opt_in_never_bypasses_regular_scheduler_lock(fixture):
    f=fixture
    with (f.event_path.parent/'scheduler.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(ValueError,match='regular scheduler is active'):
            subject.regrade([f.name],'Fairness repair.',cal=f.cal,runner=f.runner,
                allow_unrelated_diagnostic=True,diagnostic_tasks=['h6-test-unrelated'])
    assert not f.calls


def test_target_start_during_opt_in_regrade_is_retained_failure(fixture):
    f=fixture;diagnostic(f)
    def runner(*args,**kwargs):
        result=f.runner(*args,**kwargs);diagnostic(f,f.task_id+'/v3-minimax-m2-7');return result
    with (f.event_path.parent/'diagnostic.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(ValueError,match='evidence retained'):
            subject.regrade([f.name],'Fairness repair.',cal=f.cal,runner=runner,
                allow_unrelated_diagnostic=True,diagnostic_tasks=['h6-test-unrelated'])
    event=subject.events(f.event_path)[-1]
    assert not event['succeeded'] and 'target task has live' in event['error']
    assert event['raw_evidence_unchanged'] and (f.root/event['history_directory']/event['before_grade']).exists()


def test_other_task_diagnostic_events_can_append_during_regrade(fixture):
    f=fixture;diagnostic(f)
    def runner(*args,**kwargs):
        append(f,{'event':'finish','run':'h6-test-unrelated/v2-minimax-m2-7','revision':'v2'})
        diagnostic(f,'h6-test-unrelated-two/v2-minimax-m2-7')
        return f.runner(*args,**kwargs)
    with (f.event_path.parent/'diagnostic.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=subject.regrade([f.name],'Fairness repair.',cal=f.cal,runner=runner,
            allow_unrelated_diagnostic=True,diagnostic_tasks=['h6-test-unrelated','h6-test-unrelated-two'])
    assert result[0]['succeeded']


@pytest.mark.parametrize('mode',['grade-bytes','record-bytes','unfrozen-writers','orphan-history','frozen-round','historical-validation'])
def test_stronger_evidence_guards(fixture,mode):
    f=fixture
    if mode=='grade-bytes':write(f.run/'grade.json',dict(f.old,verified_success=False))
    elif mode in ('record-bytes','unfrozen-writers'):
        record=subject.read(f.run/'record.json')
        if mode=='record-bytes':record['unexpected']='modified'
        else:record['snapshot']['writers_frozen']=False
        write(f.run/'record.json',record)
    elif mode=='orphan-history':write(f.run/'grade-history/orphan/started.json',{'event':'regrade'})
    elif mode=='frozen-round':write(f.cal.HERE/'FREEZE_MANIFEST.json',{})
    else:(f.cal.HERE/'validation/fixture-validation.json').write_text('{}')
    with pytest.raises((ValueError,AssertionError)):invoke(f)
    assert not f.calls


def test_start_finish_metadata_and_consumer_fields(fixture):
    f=fixture;event=invoke(f)[0];folder=f.root/event['history_directory'];started=subject.read(folder/'started.json')
    assert event['event']=='regrade' and started['event']=='regrade'
    assert subject.date(event['started_at'])<=subject.date(event['ended_at'])
    assert event['started_sha256']==subject.sha(folder/'started.json')
    assert event['command_log_sha256']==subject.sha(folder/'command.log')
    assert all(started[k]==event[k] for k in ['run','run_id','before_grade_sha256','before_grader_hash','task_hash','source_archive'])
    assert subject.sha(f.cal.HERE/'validation'/(event['validation_run']+'.json'))==event['validation_sha256']
    assert set(event['before_flags'])==set(subject.FLAGS)==set(event['after_flags'])


def test_failed_or_orphan_regrade_is_not_automatically_retried(fixture):
    f=fixture
    def runner(*args,**kwargs):f.runner(*args,**kwargs);return SimpleNamespace(returncode=2)
    with pytest.raises(ValueError):invoke(f,runner=runner)
    calls=len(f.calls)
    with pytest.raises(ValueError,match='Prior failed regrade'):invoke(f)
    assert len(f.calls)==calls
