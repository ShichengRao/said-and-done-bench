"""Mocked subprocess tests only: no Docker, model inference, or real validation runs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import threading
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

spec = importlib.util.spec_from_file_location('parallel_validation_subject', Path(__file__).with_name('validate_parallel.py'))
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    root.mkdir()
    wrapper = root / 'heldout6/_shared/validate_parallel.py'
    for path in [wrapper, root / 'tests/test_tasks.py', root / 'tests/task_helpers.py', root / 'pyproject.toml', root / 'uv.lock']:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture\n')
    tasks = ['h6-test-one', 'h6-test-two']
    for name in tasks:
        task = root / 'heldout6' / name
        (task / 'workspace').mkdir(parents=True)
        (task / 'grader').mkdir()
        (task / 'task.toml').write_text(f'id="{name}"\nfamily="heldout6-trap"\nexpected_status="complete"\ntracks=["neutral"]\n')
        (task / 'goal.md').write_text('Fixture only.\n')
        (task / 'workspace/code.py').write_text('pass\n')
        (task / 'grader/grade.py').write_text('pass\n')
        (root / 'tests' / ('test_task_' + name.replace('-', '_') + '.py')).write_text('def test_fixture(): pass\n')
    monkeypatch.setattr(subject, 'ROOT', root)
    monkeypatch.setattr(subject, 'WRAPPER', wrapper)
    monkeypatch.setattr(subject, 'harness_hash', lambda: '0' * 64)
    return root, tasks


def emit(command, stdout, *, failure=None):
    xml = Path(next(x.split('=', 1)[1] for x in command if x.startswith('--junitxml=')))
    stdout.write('mock pytest output\n')
    if failure == 'runner':
        raise OSError('mock launch failure')
    if failure == 'missing':
        return SimpleNamespace(returncode=0)
    if failure == 'malformed':
        xml.write_text('not XML')
        return SimpleNamespace(returncode=0)
    counts = dict(tests=0 if failure == 'empty' else 1, failures=int(failure == 'failed'), errors=0, skipped=int(failure == 'skipped'))
    suite = ET.Element('testsuite', {k: str(v) for k, v in counts.items()})
    if counts['tests']:
        ET.SubElement(suite, 'testcase', name='fixture', classname=command[4])
    ET.ElementTree(suite).write(xml)
    return SimpleNamespace(returncode=1 if failure == 'nonzero' else 0)


def test_default_two_workers_exactly_once_and_compatible_evidence(project):
    root, tasks = project
    lock, barrier = threading.Lock(), threading.Barrier(2)
    calls, active, peak = [], 0, 0
    def runner(command, **kwargs):
        nonlocal active, peak
        with lock:
            calls.append(command)
            first_pair = len(calls) <= 2
            active += 1
            peak = max(peak, active)
        if first_pair:
            barrier.wait(timeout=5)
        try:
            return emit(command, kwargs['stdout'])
        finally:
            with lock:
                active -= 1
    result = subject.validate(tasks, runner=runner)
    expected = [f'tests/test_task_{t.replace("-", "_")}.py' for t in tasks] + ['tests/test_tasks.py']
    assert sorted(c[4] for c in calls) == sorted(expected) and len(calls) == 3
    assert peak == 2 and result['workers'] == 2
    assert len({next(x for x in c if x.startswith('--basetemp=')) for c in calls}) == 3
    assert result['valid'] and result['source_unchanged'] and result['counts'] == dict(tests=3, failures=0, errors=0, skipped=0)
    assert result['tasks'] == result['after'] and result['dependencies'] == result['dependencies_after']
    for key in ['log', 'xml']:
        assert hashlib.sha256((root / result[key]).read_bytes()).hexdigest() == result[key + '_sha256']
    merged = ET.parse(root / result['xml']).getroot()
    assert merged.tag == 'testsuites' and len(merged.findall('testsuite')) == 3
    assert all((root / r['log']).is_file() and (root / r['xml']).is_file() for r in result['file_runs'])
    directory = root / 'heldout6/validation'
    assert json.loads((directory / (result['run_id'] + '.json')).read_text()) == result
    for task in tasks:
        assert json.loads((directory / (task + '.json')).read_text()) == result


@pytest.mark.parametrize('failure', ['failed', 'skipped', 'nonzero', 'missing', 'malformed', 'empty', 'runner'])
def test_failed_or_incomplete_file_never_updates_eligibility(project, failure):
    root, tasks = project
    directory = root / 'heldout6/validation'
    directory.mkdir()
    for task in tasks:
        (directory / (task + '.json')).write_text('preserved prior eligibility\n')
    calls = []
    def runner(command, **kwargs):
        calls.append(command[4])
        return emit(command, kwargs['stdout'], failure=failure if command[4] == 'tests/test_tasks.py' else None)
    result = subject.validate(tasks, runner=runner)
    assert not result['valid'] and result['exit_code'] != 0 and len(calls) == 3
    assert result['source_unchanged'] and len(result['file_runs']) == 3
    assert (directory / (result['run_id'] + '.json')).exists()
    for task in tasks:
        assert (directory / (task + '.json')).read_text() == 'preserved prior eligibility\n'


@pytest.mark.parametrize('relative', ['heldout6/h6-test-one/workspace/code.py', 'heldout6/h6-test-one/grader/grade.py',
                                     'tests/test_task_h6_test_one.py', 'tests/test_tasks.py',
                                     'tests/task_helpers.py', 'heldout6/_shared/validate_parallel.py'])
def test_changed_sources_or_shared_dependencies_refuse_eligibility(project, relative):
    root, tasks = project
    def runner(command, **kwargs):
        if command[4] == 'tests/test_tasks.py':
            (root / relative).write_text('changed during validation\n')
        return emit(command, kwargs['stdout'])
    result = subject.validate(tasks, runner=runner)
    assert not result['valid'] and not result['source_unchanged']
    assert all(r['valid'] for r in result['file_runs'])
    assert not any((root / 'heldout6/validation' / (task + '.json')).exists() for task in tasks)


@pytest.mark.parametrize('tasks,workers', [([], 2), (['h6-test-one'] * 2, 2), (['../h6-test-one'], 2), (['h6-test-one'], 0)])
def test_invalid_request_runs_nothing(project, tasks, workers):
    def forbidden(*args, **kwargs):
        raise AssertionError('must not launch a test')
    with pytest.raises(ValueError):
        subject.validate(tasks, workers, runner=forbidden)
