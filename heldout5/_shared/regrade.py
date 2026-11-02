"""Regrade explicitly named closed Round 5 runs, retaining every grade version.

Usage: .venv/bin/python heldout5/_shared/regrade.py h5-task/v1-model --reason 'Exact grader-only repair'
No inference is launched. The existing benchmark grade command remains authoritative.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibrate

CLOSED = {'complete', 'blocked', 'stalled', 'step_cap', 'timeout', 'infra_error'}
FLAGS = ('outcome', 'expected_status', 'passed', 'scored', 'verified_success', 'said_and_done',
         'claims_truthful', 'false_completion', 'wrongly_blocked', 'unjustified_block',
         'stale_task', 'grading_image_is_the_runs')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    require(path.is_file() and not path.is_symlink(), f'Missing or linked evidence: {path}')
    value = json.loads(path.read_text())
    require(isinstance(value, dict), f'Expected a JSON object: {path}')
    return value


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def date(value):
    require(isinstance(value, str) and bool(value), 'Missing closed-run timestamp')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'Timestamp needs an explicit timezone')
    return result


def events(path):
    require(path.is_file(), 'Missing scheduler event log')
    result = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    require(all(isinstance(e, dict) for e in result), 'Malformed scheduler event log')
    return result


def evidence(run):
    """The grading workspace and grade versions are mutable; raw run evidence is not."""
    result = {}
    for path in sorted(run.rglob('*')):
        relative = path.relative_to(run)
        if relative.parts[0] in {'grading', 'grade-history'} or relative.as_posix() == 'grade.json':
            continue
        require(not path.is_symlink(), f'Linked raw evidence: {relative}')
        if path.is_file():
            result[relative.as_posix()] = sha(path)
    require('record.json' in result and 'snapshot.tar.gz' in result, 'Missing record or snapshot')
    return result


def inspect_run(name, cal=calibrate):
    require(re.fullmatch(r'h5-[a-z0-9-]+/[a-z0-9-]+', name), 'Use an explicit h5-task/revision-model run name')
    task_id = name.split('/')[0]
    run = cal.RUNS / name
    require(run.is_dir() and run.resolve().relative_to(cal.RUNS.resolve()).as_posix() == name, 'Missing or linked run directory')
    record = read(run / 'record.json')
    old = read(run / 'grade.json')
    require(record.get('outcome') in CLOSED, 'Run has no closed terminal outcome')
    ended = date(record.get('ended_at'))
    require(ended >= date(record.get('started_at')), 'Run timestamps are inconsistent')
    task = record.get('task') or {}
    require(task.get('id') == task_id, 'Record task identity does not match run directory')
    require(Path(task.get('path', '')).resolve() == (cal.HERE / task_id).resolve(), 'Recorded task path differs from current Round 5 task')
    identity = cal.validated_identity(task_id)
    validation_path = cal.HERE / 'validation' / f'{task_id}.json'
    validation = read(validation_path)
    counts = validation.get('counts') or {}
    require(validation.get('exit_code') == 0 and counts.get('tests', 0) > 0
            and all(counts.get(k) == 0 for k in ('failures', 'errors', 'skipped')),
            'Validation has missing or failing checks')
    require(validation.get('tasks', {}).get(task_id) == validation.get('after', {}).get(task_id),
            'Validation source changed during checks')
    require(task.get('task_hash') == identity['task_hash'], 'Task inputs changed; a regrade cannot repair inference on different inputs')
    require(task.get('harness_hash') == cal.harness_hash(), 'Recorded harness differs from current harness')
    require(old.get('task') == task_id and old.get('outcome') == record['outcome'], 'Old grade identity differs from the closed record')
    require(old.get('expected_status') == task.get('expected_status'), 'Old grade expected status differs from record')
    require(old.get('stale_task') is False, 'Old grade reports stale task inputs')
    require(re.fullmatch(r'[0-9a-f]{64}', old.get('grader_hash', '')), 'Old grade has no valid grader hash')
    history = events(cal.RUNS / 'control/events.jsonl')
    starts = [i for i, e in enumerate(history) if e.get('event') == 'start' and e.get('run') == name]
    require(bool(starts), 'No scheduler start event for this run')
    start_index = starts[-1]
    start = history[start_index]
    require(start.get('task_hash') == identity['task_hash'], 'Scheduler start used different task inputs')
    finishes = [(i, e) for i, e in enumerate(history) if i > start_index and e.get('event') == 'finish' and e.get('run') == name]
    require(bool(finishes), 'Run has no scheduler finish event; it may still be active')
    finish_index, finish = finishes[-1]
    require(finish.get('outcome') == record['outcome'] and finish.get('mutated_during_run') is False,
            'Scheduler finish is inconsistent or sources changed during inference')
    require(date(finish.get('at')) >= ended, 'Scheduler finish precedes recorded end')
    require(any(i > finish_index and e.get('event') == 'scheduler_finished' and e.get('revision') == start.get('revision')
                for i, e in enumerate(history)), 'The run scheduler has not recorded completion')
    prior = [e for e in history if e.get('event') == 'regrade' and e.get('run') == name]
    if prior:
        require(prior[-1].get('after_grade_sha256') == sha(run / 'grade.json')
                and prior[-1].get('after_grader_hash') == old['grader_hash'], 'Current grade differs from recorded regrade history')
    else:
        require(old['grader_hash'] == start.get('grader_hash'), 'Old grade has changed without retained regrade provenance')
    return {'run': run, 'record': record, 'old': old, 'identity': identity,
            'raw': evidence(run), 'validation_sha256': sha(validation_path),
            'validation_run': validation['run_id'], 'revision': start['revision'],
            'old_sha256': sha(run / 'grade.json')}


def exclusive_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def append_event(path, event):
    with path.open('a') as stream:
        stream.write(json.dumps(event, sort_keys=True) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def perform(name, state, reason, cal, runner):
    run = state['run']
    identity = state['identity']
    source_archive = cal.archive_source(identity)
    require(evidence(run) == state['raw'] and sha(run / 'grade.json') == state['old_sha256'], 'Run evidence changed before archiving')
    attempt = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex
    directory = run / 'grade-history' / attempt
    directory.mkdir(parents=True, exist_ok=False)
    before_name = 'before-' + state['old']['grader_hash'] + '-' + state['old_sha256'] + '.json'
    with (directory / before_name).open('xb') as stream:
        stream.write((run / 'grade.json').read_bytes())
        stream.flush()
        os.fsync(stream.fileno())
    require(sha(directory / before_name) == state['old_sha256'], 'Old grade changed while being archived')
    command = [cal.PYTHON, '-m', 'beambench', 'grade', str(run)]
    event = {'event': 'regrade', 'at': cal.stamp(), 'run': name, 'run_id': state['record']['run_id'],
             'revision': state['revision'], 'reason': reason, 'command': command,
             'task_hash': identity['task_hash'], 'harness_hash': state['record']['task']['harness_hash'],
             'source_archive': source_archive,
             'validation_run': state['validation_run'], 'validation_sha256': state['validation_sha256'],
             'test_sha256': identity['test_sha256'], 'before_grade_sha256': state['old_sha256'],
             'before_grader_hash': state['old']['grader_hash'],
             'before_flags': {k: state['old'].get(k) for k in FLAGS},
             'raw_evidence_sha256': state['raw'],
             'history_directory': str(directory.relative_to(cal.ROOT)),
             'before_grade': before_name}
    exclusive_json(directory / 'started.json', event)
    error = None
    code = None
    try:
        with (directory / 'command.log').open('xb') as log:
            result = runner(command, cwd=cal.ROOT,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                            stdout=log, stderr=subprocess.STDOUT, check=False)
        code = result.returncode
        require(code == 0, f'Grade command exited {code}')
        after = read(run / 'grade.json')
        require(after.get('task') == identity['task'] and after.get('outcome') == state['record']['outcome'], 'New grade identity changed')
        require(after.get('grader_hash') == identity['grader_hash'] and after.get('stale_task') is False, 'New grade does not use validated current sources')
        require(after.get('expected_status') == state['record']['task']['expected_status'], 'New expected status changed')
        require(after.get('grading_image_is_the_runs') is True, 'New grade used a different image')
        require('grader_error' not in (after.get('checks') or {}), 'New grader failed; retain its unscored result for review')
        require(cal.validated_identity(identity['task']) == identity, 'Validated identity changed during regrading')
        require(sha(cal.HERE / 'validation' / f"{identity['task']}.json") == state['validation_sha256'], 'Validation record changed during regrading')
        require(evidence(run) == state['raw'], 'Raw inference evidence changed during regrading')
        cal.verify_baseline()
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    # Even failed postchecks preserve exactly what the grade command wrote; no flags are repaired here.
    after = {}
    after_sha = None
    after_name = None
    if (run / 'grade.json').is_file() and not (run / 'grade.json').is_symlink():
        after_sha = sha(run / 'grade.json')
        after_name = 'after-' + after_sha + '.json'
        with (directory / after_name).open('xb') as stream:
            stream.write((run / 'grade.json').read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        try:
            after = read(run / 'grade.json')
        except (ValueError, OSError):
            pass
    try:
        unchanged = evidence(run) == state['raw']
    except (ValueError, OSError):
        unchanged = False
    event.update(at=cal.stamp(), command_exit_code=code, succeeded=error is None, error=error,
                 after_grade_sha256=after_sha, after_grader_hash=after.get('grader_hash'),
                 after_flags={k: after.get(k) for k in FLAGS}, after_grade=after_name,
                 raw_evidence_unchanged=unchanged)
    exclusive_json(directory / 'event.json', event)
    append_event(cal.RUNS / 'control/events.jsonl', event)
    if error:
        raise ValueError(f'Regrade evidence retained in {directory}: {error}')
    return event


def regrade(names, reason, *, cal=calibrate, runner=subprocess.run):
    require(names and len(set(names)) == len(names), 'Name one or more distinct closed runs explicitly')
    require(isinstance(reason, str) and bool(reason.strip()), 'An exact grader-only repair reason is required')
    control = cal.RUNS / 'control'
    require(control.is_dir(), 'Missing Round 5 scheduler control directory')
    with (control / 'scheduler.lock').open('a') as lock, (control / 'diagnostic.lock').open('a') as diagnostic:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(diagnostic, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Round 5 scheduler is active; wait until all inference closes') from None
        cal.verify_baseline()
        # Validate the entire explicit list before modifying any grade.
        for name in names:
            inspect_run(name, cal)
        return [perform(name, inspect_run(name, cal), reason, cal, runner) for name in names]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', help='Explicit h5-task/revision-model names under runs/calibration-h5')
    parser.add_argument('--reason', required=True)
    args = parser.parse_args()
    try:
        result = regrade(args.runs, args.reason)
    except (AssertionError, ValueError, OSError, KeyError) as error:
        raise SystemExit(str(error)) from error
    for event in result:
        print(json.dumps(event, sort_keys=True))


if __name__ == '__main__':
    main()
