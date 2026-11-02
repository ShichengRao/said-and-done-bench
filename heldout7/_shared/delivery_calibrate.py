"""Run one fresh MiniMax attempt per validated delivery task, in bounded batches.

Opus cloud sessions are a separate execution profile and are not dispatched here.
The unchanged local harness enforces the 900-second neutral run deadline.
"""
from __future__ import annotations
import argparse
import asyncio
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from beambench.tasks import load_task, task_hash, grader_hash, harness_hash
spec = importlib.util.spec_from_file_location('h6_calibration', ROOT/'heldout6/_shared/calibrate.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
RUNS = ROOT/'runs/calibration-h7-delivery'
PYTHON = ROOT/'.venv/bin/python'


def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()


def run_costs(base):
    total = 0.0
    for run in base.glob('h7-*/*'):
        record = read(run/'record.json') if (run/'record.json').exists() else {}
        cost = (record.get('usage_total') or {}).get('cost')
        if cost is not None:
            total += cost
        elif (run/'neutral.jsonl').exists():
            for line in (run/'neutral.jsonl').read_text().splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue  # An in-flight final line is not a closed response.
                total += ((row.get('response') or {}).get('usage') or {}).get('cost', 0) or 0
    return total


def combined_cost():
    return prior.recorded_cost() + run_costs(ROOT/'runs/calibration-h7') + run_costs(RUNS)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validation', type=Path, required=True)
    parser.add_argument('--concurrency', type=int, default=2, choices=range(1, 5))
    args = parser.parse_args()
    validation_path = args.validation.resolve()
    validation = read(validation_path)
    assert validation['passed'] and validation['source_reviewed']
    config = prior.verify_configs()
    expected = config['neutral']['h6-minimax-m2-7-thinking']
    expected_limits = {**config['limits'], 'run_deadline_s': 900.0}
    assert harness_hash() == config['harness_hash']
    assert not (ROOT/'ready.txt').exists()
    tasks = validation['tasks']
    assert len({t['task'] for t in tasks}) == len(tasks)
    for x in tasks:
        task = load_task(ROOT/x['path'])
        assert task.id == x['task'] and task.family == 'heldout7-delivery'
        assert task.command_timeout_s == 120
        assert task_hash(task) == x['task_hash'] and grader_hash(task) == x['grader_hash']
    control = RUNS/'control'
    control.mkdir(parents=True, exist_ok=True)
    with (control/'batch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stop = asyncio.Event()
        semaphore = asyncio.Semaphore(args.concurrency)
        pins = {str(validation_path): sha(validation_path), str(Path(__file__)): sha(Path(__file__))}
        for relative, digest in validation['test_file_sha256'].items():
            path = (ROOT/relative).resolve()
            assert path.is_relative_to(ROOT) and sha(path) == digest
            pins[str(path)] = digest

        def emit(event):
            row = {'at': now(), **event}
            with (control/'events.jsonl').open('a') as out:
                out.write(json.dumps(row)+'\n')
            print(json.dumps(row), flush=True)

        async def command(argv, log):
            with log.open('xb') as output:
                proc = await asyncio.create_subprocess_exec(*map(str, argv), cwd=ROOT,
                    env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                    stdout=output, stderr=asyncio.subprocess.STDOUT)
                return await proc.wait()

        async def one(x):
            async with semaphore:
                if stop.is_set(): return
                # Reserve headroom under the existing $10 scheduling threshold.
                # Provider billing for failed/in-flight requests can arrive later.
                spent = combined_cost()
                if spent >= 9.0:
                    stop.set()
                    emit({'event': 'budget_stop', 'recorded_combined_usd': spent})
                    return
                assert all(sha(Path(p)) == v for p, v in pins.items())
                assert prior.verify_configs() == config
                task = load_task(ROOT/x['path'])
                assert task_hash(task) == x['task_hash'] and grader_hash(task) == x['grader_hash']
                run = RUNS/x['task']/'attempt1-minimax-m2-7'
                assert not run.exists(), 'Existing attempts are retained, never automatically rerun.'
                archive = ROOT/'heldout7/_history'/x['task']/(x['task_hash']+'-'+x['grader_hash'])
                if not archive.exists():
                    archive.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(task.path, archive, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
                assert task_hash(load_task(archive)) == x['task_hash']
                emit({'event':'start', 'model':'minimax-m2-7', 'task':x['task'], 'source':x,
                      'run':str(run.relative_to(ROOT)), 'profile':'delivery-900s-v1', 'runtime_pins':pins})
                code = await command([PYTHON, ROOT/'heldout6/_shared/run_configured.py', 'run',
                    '--agent','neutral','--model-config','h6-minimax-m2-7-thinking',
                    '--task',task.path,'--run-dir',run,'--run-deadline','900'],
                    control/(x['task']+'-minimax.log'))
                issues = []
                if not (run/'record.json').exists():
                    stop.set(); emit({'event':'missing_record','task':x['task'],'exit_code':code}); return
                record = read(run/'record.json')
                info = record.get('agent_info') or {}
                actual = prior.response_identity(run)
                if record.get('limits') != expected_limits: issues.append('limits')
                if any(info.get(k) != expected[k] for k in ('model','base_url','params')): issues.append('request identity')
                if actual['models'] != {expected['model']} or actual['providers'] != {'Minimax'} or actual['malformed']:
                    issues.append('returned model/provider')
                if not actual['reasoning']: issues.append('no reasoning evidence')
                rt = record.get('task') or {}
                if rt.get('task_hash') != x['task_hash'] or rt.get('harness_hash') != config['harness_hash']:
                    issues.append('task/harness identity')
                if rt.get('image_id') != config['images']['image_id']: issues.append('task image')
                if not record.get('ended_at'): issues.append('unclosed record')
                if record.get('outcome') != 'infra_error' and (record.get('snapshot') or {}).get('writers_frozen') is not True:
                    issues.append('snapshot not frozen')
                if not (run/'grade.json').exists() and (run/'snapshot.tar.gz').exists() and not issues:
                    await command([PYTHON,'-m','beambench','grade',run],control/(x['task']+'-grade.log'))
                grade = read(run/'grade.json') if (run/'grade.json').exists() else {}
                if grade and (grade.get('grader_hash') != x['grader_hash'] or grade.get('stale_task') is not False):
                    issues.append('grader identity')
                assert task_hash(task) == x['task_hash'] and grader_hash(task) == x['grader_hash']
                assert all(sha(Path(p)) == v for p, v in pins.items())
                emit({'event':'finish','task':x['task'],'exit_code':code,'outcome':record.get('outcome'),
                      'scored':grade.get('scored'),'verified_success':grade.get('verified_success'),
                      'semantic_review_status':(grade.get('checks') or {}).get('semantic_review_status'),
                      'issues':issues,'record_sha256':sha(run/'record.json'),
                      'recorded_combined_usd':combined_cost()})
                if issues or code or record.get('outcome') == 'infra_error': stop.set()

        await asyncio.gather(*(one(x) for x in tasks))
        emit({'event':'batch_finished','stopped':stop.is_set(),'recorded_combined_usd':combined_cost()})


if __name__ == '__main__': asyncio.run(main())
