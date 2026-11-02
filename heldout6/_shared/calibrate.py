"""Schedule validated Round 6 tasks through the unchanged benchmark CLI."""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from beambench.neutral import load_models
from beambench.tasks import load_task, task_hash, grader_hash, harness_hash

HERE = ROOT / 'heldout6'
RUNS = ROOT / 'runs/calibration-h6'
PYTHON = str(ROOT / '.venv/bin/python')
CONFIG_NAMES = {'deepseek-v3': 'deepseek-v3', 'flash': 'deepseek-v4-1-flash',
                'minimax-m2-7': 'h6-minimax-m2-7-thinking'}
PROVIDERS = {'deepseek-v3': 'StreamLake', 'flash': 'DeepInfra', 'minimax-m2-7': 'Minimax'}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_run(path):
    return tuple(json.loads((path / name).read_text()) if (path / name).exists() else {}
                 for name in ('record.json', 'grade.json'))


def recorded_cost():
    total = 0.0
    for run in RUNS.glob('h6-*/*'):
        if not run.is_dir():
            continue
        record, _ = read_run(run)
        cost = (record.get('usage_total') or {}).get('cost')
        if cost is not None:
            total += cost
            continue
        transcript = run / 'neutral.jsonl'
        if transcript.exists():
            for line in transcript.read_text().splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                total += ((event.get('response') or {}).get('usage') or {}).get('cost', 0) or 0
    return total


def verify_baseline():
    pins = json.loads((HERE / 'PRESERVED_BASELINES.json').read_text())['manifest_sha256']
    checked = {}
    for name, expected in pins.items():
        assert sha(ROOT / name) == expected, ('Preserved manifest changed', name)
        manifest = json.loads((ROOT / name).read_text())
        for group in ('source_file_sha256', 'permitted_harness_file_sha256',
                      'raw_evidence_sha256', 'prior_evidence_sha256',
                      'prior_manifest_sha256', 'preserved_evidence_sha256'):
            for relative, digest in manifest.get(group, {}).items():
                path = Path(relative)
                assert not path.is_absolute() and '..' not in path.parts
                assert relative not in checked or checked[relative] == digest
                if relative not in checked:
                    assert sha(ROOT / path) == digest, ('Preserved evidence changed', relative)
                    checked[relative] = digest
    assert harness_hash() == json.loads((HERE/'MODEL_CONFIGS.json').read_text())['harness_hash'], 'Harness changed'


def response_identity(run):
    result = {'responses': 0, 'models': set(), 'providers': set(), 'reasoning': 0, 'malformed': 0}
    path = run / 'neutral.jsonl'
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                response = json.loads(line).get('response')
            except (ValueError, AttributeError):
                result['malformed'] += 1
                continue
            if not isinstance(response, dict):
                continue
            result['responses'] += 1
            result['models'].add(response.get('model'))
            result['providers'].add(response.get('provider'))
            messages = [c.get('message', {}) for c in response.get('choices', []) if isinstance(c, dict)]
            if any(any(m.get(k) for k in ('reasoning', 'reasoning_content', 'reasoning_details')) for m in messages):
                result['reasoning'] += 1
    return result


def verify_configs():
    config = json.loads((HERE / 'MODEL_CONFIGS.json').read_text())
    models = load_models()
    for name, expected in config['neutral'].items():
        assert dataclasses.asdict(models[name]) == expected, ('Model configuration changed', name)
    extra = json.loads((HERE / 'ADDITIONAL_MODEL_CONFIGS.json').read_text())
    extra_models = load_models(HERE / 'ADDITIONAL_MODELS.toml')
    for name, expected in extra['neutral'].items():
        assert name not in config['neutral'], ('Additional model shadows an anchor', name)
        assert dataclasses.asdict(extra_models[name]) == expected, ('Additional configuration changed', name)
        config['neutral'][name] = expected
    config['additional_diagnostic_lane'] = extra['additional_diagnostic_lane']
    config['combined_neutral_concurrency'] = extra['combined_neutral_concurrency']
    diagnostic = config['additional_diagnostic_lane']
    assert diagnostic['model'] == 'minimax-m2-7' and diagnostic['max_concurrent'] in (1, 3)
    assert config['neutral_concurrency'] == 1 and config['combined_neutral_concurrency'] == 1 + diagnostic['max_concurrent']
    assert config['strong']['authentication_lanes'] == ['codex-2', 'codex-3']
    config['runtime_sha256'] = {name: sha(HERE / name) for name in (
        'MODEL_CONFIGS.json', 'ADDITIONAL_MODEL_CONFIGS.json', 'ADDITIONAL_MODELS.toml',
        'PRESERVED_BASELINES.json', '_shared/calibrate.py', '_shared/run_configured.py', '_shared/validate.py')}
    return config


def validated_identity(task_id):
    spec = load_task(HERE / task_id)
    validation = json.loads((HERE / 'validation' / f'{task_id}.json').read_text())
    expected = validation['tasks'][task_id]
    assert validation['valid'] and validation['source_unchanged'], ('Invalid validation', task_id)
    assert task_hash(spec) == expected['task_hash'], ('Unvalidated task change', task_id)
    assert grader_hash(spec) == expected['grader_hash'], ('Unvalidated grader change', task_id)
    assert sha(ROOT / expected['test_file']) == expected['test_sha256'], ('Changed tests', task_id)
    assert sha(ROOT / validation['log']) == validation['log_sha256'], ('Changed validation log', task_id)
    assert sha(ROOT / validation['xml']) == validation['xml_sha256'], ('Changed validation XML', task_id)
    return {'task': task_id, **expected}



def existing_grade_issues(run, identity, model, config):
    """A present grade is evidence: verify it, never silently replace it."""
    record, grade = read_run(run)
    task = record.get('task') or {}; info = record.get('agent_info') or {}; images = config['images']
    issues = []
    def check(ok, reason):
        if not ok: issues.append(reason)
    check(bool(record.get('ended_at')) and record.get('outcome') in
          {'complete','blocked','stalled','step_cap','timeout','infra_error'}, 'record is not closed')
    check(task.get('id') == identity['task'] and task.get('task_hash') == identity['task_hash'], 'record task identity differs')
    check(task.get('harness_hash') == config['harness_hash'], 'record harness differs')
    check(task.get('image') == images['image'] and task.get('image_id') == images['image_id'], 'record task image differs')
    check(record.get('limits') == config['limits'], 'run limits differ')
    check((record.get('snapshot') or {}).get('writers_frozen') is True, 'snapshot writers were not frozen')
    if model == 'astra':
        check(task.get('agent') == 'codex' and task.get('track') == 'native', 'native track differs')
        check(info.get('model') == config['strong']['model'] and info.get('effort') == config['strong']['effort'], 'native model or effort differs')
        check(task.get('agent_image') == images['agent_image'] and task.get('agent_image_id') == images['agent_image_id'], 'native image differs')
    else:
        expected = config['neutral'][CONFIG_NAMES[model]]
        check(task.get('agent') == 'neutral' and task.get('track') == 'neutral', 'neutral track differs')
        check(all(info.get(k) == expected[k] for k in ('model','base_url','params')) and info.get('model_config') == expected['name'], 'neutral model configuration differs')
        check(task.get('agent_image') == images['image'] and task.get('agent_image_id') == images['image_id'], 'neutral image differs')
        response = response_identity(run)
        check(response['malformed'] == 0 and response['responses'] > 0, 'returned response evidence missing or malformed')
        check(response['models'] == {expected['model']}, 'returned model identity differs')
        check(response['providers'] == {PROVIDERS[model]}, 'returned provider identity differs')
        if model == 'minimax-m2-7':
            check(response['reasoning'] > 0, 'no returned thinking content')
    check((run/'snapshot.tar.gz').is_file(), 'snapshot missing')
    check(grade.get('task') == identity['task'] and grade.get('outcome') == record.get('outcome')
          and grade.get('expected_status') == task.get('expected_status'), 'grade identity differs')
    check(grade.get('grader_hash') == identity['grader_hash'], 'grade uses another grader')
    check(grade.get('stale_task') is False, 'grade is stale or has no staleness evidence')
    check(grade.get('grading_image_is_the_runs') is True and grade.get('grading_image') in
          {images['image'],images['image_id']}, 'grade image differs')
    check(grade.get('scored') is True and 'grader_error' not in (grade.get('checks') or {}), 'grade is unscored or failed')
    return issues


def archive_source(identity):
    task_id = identity['task']
    destination = HERE / '_history' / task_id / (identity['task_hash'] + '-' + identity['grader_hash'])
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(HERE / task_id, destination,
                        ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '*.pyc'))
    archived = load_task(destination)
    assert task_hash(archived) == identity['task_hash']
    assert grader_hash(archived) == identity['grader_hash']
    return str(destination.relative_to(ROOT))


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tasks', nargs='+')
    parser.add_argument('--revision', required=True)
    parser.add_argument('--models', nargs='+', choices=['astra', *CONFIG_NAMES],
                        default=['astra', 'deepseek-v3', 'flash'])
    parser.add_argument('--repeat-reason', help='Required to repeat a model on unchanged task inputs')
    parser.add_argument('--diagnostic-lane', action='store_true',
                        help='Exclusive MiniMax scheduler; shares the round cost counter')
    parser.add_argument('--diagnostic-concurrency', type=int, choices=(1,3), default=1,
                        help='Independent task attempts within the exclusive diagnostic scheduler')
    args = parser.parse_args()
    if args.diagnostic_lane and args.models != ['minimax-m2-7']:
        parser.error('the independent diagnostic lane is exclusively for MiniMax M2.7')
    if 'minimax-m2-7' in args.models and not args.diagnostic_lane:
        parser.error('MiniMax M2.7 must use its exclusive diagnostic lane')
    if args.diagnostic_concurrency != 1 and not args.diagnostic_lane:
        parser.error('Additional workers are exclusive to the MiniMax diagnostic')
    if not re.fullmatch(r'[a-z0-9-]+', args.revision):
        parser.error('revision must contain lowercase letters, digits, or hyphens')
    if len(set(args.tasks)) != len(args.tasks) or len(set(args.models)) != len(args.models):
        parser.error('duplicate tasks or models')
    if any(not re.fullmatch(r'h6-[a-z0-9-]+', task_id) for task_id in args.tasks):
        parser.error('use explicit h5 task IDs')
    verify_baseline()
    config = verify_configs()
    for image_key, id_key in [('image', 'image_id'), ('agent_image', 'agent_image_id')]:
        actual = subprocess.check_output(['docker', 'image', 'inspect', config['images'][image_key],
                                          '--format', '{{.Id}}'], text=True).strip()
        assert actual == config['images'][id_key], 'Pinned container image differs'
    if args.diagnostic_concurrency > config['additional_diagnostic_lane']['max_concurrent']:
        parser.error('Diagnostic concurrency exceeds the reviewed configuration')
    identities = [validated_identity(task_id) for task_id in args.tasks]
    for identity in identities:
        identity['source_archive'] = archive_source(identity)
    control = RUNS / 'control'
    control.mkdir(parents=True, exist_ok=True)
    lock_name = 'diagnostic.lock' if args.diagnostic_lane else 'scheduler.lock'
    with (control / lock_name).open('a') as scheduler_lock:
        try:
            fcntl.flock(scheduler_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another Round 6 scheduler is active in this lane')
        await schedule(args, identities, config, control)


async def schedule(args, identities, config, control):
    event_path = control / 'events.jsonl'
    halt_all = asyncio.Event()
    halted = {model: asyncio.Event() for model in args.models}
    strong_queue = asyncio.Queue()
    for identity in identities:
        strong_queue.put_nowait(identity)

    def emit(event):
        event = {'at': stamp(), 'revision': args.revision, **event}
        with event_path.open('a') as stream:
            stream.write(json.dumps(event) + '\n')
        print(json.dumps(event), flush=True)

    def stop(model, reason, run=None):
        halted[model].set()
        (control / f'STOP_{model}').write_text(json.dumps({'at': stamp(), 'run': run, 'reason': reason}) + '\n')
        emit({'event': 'halt', 'model': model, 'run': run, 'reason': reason})

    async def command(argv, env, log):
        with log.open('xb') as stream:
            process = await asyncio.create_subprocess_exec(*argv, cwd=ROOT, env=env,
                stdout=stream, stderr=asyncio.subprocess.STDOUT)
            return await process.wait()

    async def run_one(identity, model, lane=None):
        if halt_all.is_set() or halted[model].is_set() or (control / f'STOP_{model}').exists():
            return
        spent = recorded_cost()
        if spent >= config['scheduling_cost_threshold_usd']:
            halt_all.set()
            emit({'event': 'halt_all', 'reason': 'API scheduling cost threshold reached', 'recorded_cost': spent})
            return
        assert verify_configs() == config, 'Runtime configuration changed during scheduling'
        current = validated_identity(identity['task'])
        assert all(current[key] == value for key, value in identity.items() if key != 'source_archive')
        run = RUNS / identity['task'] / f'{args.revision}-{model}'
        name = str(run.relative_to(RUNS))
        if run.exists():
            record, grade = read_run(run)
            problems = existing_grade_issues(run, identity, model, config)
            if problems or record.get('outcome') == 'infra_error':
                stop(model, 'Existing attempt requires explicit preserving review/regrade: ' + '; '.join(problems), name)
                return
            emit({'event': 'already_recorded', 'run': name, 'model': model})
            return
        previous_attempts = []
        for previous in (RUNS / identity['task']).glob(f'*-{model}'):
            record, _ = read_run(previous)
            if record.get('task', {}).get('task_hash') == identity['task_hash']:
                previous_attempts.append(str(previous.relative_to(RUNS)))
        if previous_attempts and not (args.repeat_reason or '').strip():
            stop(model, 'Same task inputs were already attempted; explicit repeat reason required', name)
            return
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
        argv = [PYTHON, '-m', 'beambench', 'run']
        if model == 'astra':
            assert lane in (2, 3)
            env['BEAMBENCH_CODEX_AUTH'] = str(Path.home() / '.config/beambench' / f'codex-{lane}')
            argv += ['--agent', 'codex', '--model', 'gpt-6-astra', '--effort', 'max']
        else:
            if model == 'minimax-m2-7':
                argv = [PYTHON, str(HERE / '_shared/run_configured.py'), 'run']
            argv += ['--agent', 'neutral', '--model-config', CONFIG_NAMES[model]]
        argv += ['--task', str(HERE / identity['task']), '--run-dir', str(run), '--run-deadline', '2700']
        log_prefix = name.replace('/', '-')
        emit({'event': 'start', 'run': name, 'model': model, 'lane': lane,
              'repeat_reason': args.repeat_reason, 'previous_same_input_attempts': previous_attempts,
              'runtime_sha256': config['runtime_sha256'], **identity})
        started = time.monotonic()
        exit_code = await command(argv, env, control / f'{log_prefix}.log')
        record, grade = read_run(run)
        after = load_task(HERE / identity['task'])
        changed = (task_hash(after) != identity['task_hash']
                   or grader_hash(after) != identity['grader_hash'])
        grade_code = None
        if record and (run / 'snapshot.tar.gz').exists() and not changed:
            if (run / 'grade.json').exists():
                problems = existing_grade_issues(run, identity, model, config)
                if problems:
                    stop(model, 'Present grade retained; explicit preserving regrade required: ' + '; '.join(problems), name)
                else:
                    grade_code = 0
                    emit({'event': 'existing_grade_retained', 'run': name, 'model': model,
                          'grade_sha256': sha(run / 'grade.json'), 'grader_hash': grade['grader_hash']})
            else:
                grade_code = await command([PYTHON, '-m', 'beambench', 'grade', str(run)], env,
                                           control / f'{log_prefix}-grade.log')
                record, grade = read_run(run)
        try:
            verify_baseline()
            assert verify_configs() == config, 'Runtime configuration changed during inference'
        except (AssertionError, OSError, ValueError) as error:
            halt_all.set()
            emit({'event': 'halt_all', 'reason': 'Baseline verification failed', 'detail': str(error)})
        identity_issues = existing_grade_issues(run, identity, model, config)
        emit({'event': 'finish', 'run': name, 'model': model, 'lane': lane,
              'exit_code': exit_code, 'grade_exit_code': grade_code,
              'identity_issues': identity_issues,
              'record_sha256': sha(run/'record.json') if (run/'record.json').exists() else None,
              'grade_sha256': sha(run/'grade.json') if (run/'grade.json').exists() else None,
              'seconds': round(time.monotonic() - started, 2), 'mutated_during_run': changed,
              'outcome': record.get('outcome'), 'usage': record.get('usage_total'),
              **{key: grade.get(key) for key in
                 ['verified_success', 'said_and_done', 'claims_truthful', 'scored', 'false_completion', 'unjustified_block', 'stale_task']}})
        if changed:
            halt_all.set()
            emit({'event': 'halt_all', 'reason': 'Source changed during inference', 'run': name})
        if (identity_issues or exit_code != 0 or not record or record.get('outcome') == 'infra_error' or not grade.get('scored')
                or grade.get('stale_task') or grade_code != 0):
            stop(model, 'Infrastructure, authentication, provider, or grading failure requires inspection', name)

    async def safe_run(identity, model, lane=None):
        try:
            await run_one(identity, model, lane)
        except (AssertionError, OSError, ValueError, KeyError) as error:
            halt_all.set()
            stop(model, f'Validation or scheduling error: {error}', identity['task'])

    async def strong_lane(lane):
        auth = Path.home() / '.config/beambench' / f'codex-{lane}'
        lock_id = hashlib.sha256(str(auth).encode()).hexdigest()[:20]
        # Retain the old lock name so an earlier round using this wrapper cannot share a sign-in.
        with (Path('/tmp') / f'beambench-h4-auth-{lock_id}.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                stop('astra', 'Authentication lane already locked')
                return
            while not strong_queue.empty() and not halted['astra'].is_set() and not halt_all.is_set():
                item = strong_queue.get_nowait()
                await safe_run(item, 'astra', lane)
                strong_queue.task_done()

    async def neutral_lane():
        # One neutral request stream at a time limits provider pressure and spend.
        for identity in identities:
            for model in CONFIG_NAMES:
                if model in args.models:
                    await safe_run(identity, model)

    diagnostic_queue = asyncio.Queue()
    for identity in identities:
        diagnostic_queue.put_nowait(identity)

    async def diagnostic_worker(lane):
        while not diagnostic_queue.empty() and not halted['minimax-m2-7'].is_set() and not halt_all.is_set():
            item = diagnostic_queue.get_nowait()
            await safe_run(item, 'minimax-m2-7', lane)
            diagnostic_queue.task_done()

    workers = []
    if 'astra' in args.models:
        workers.extend(strong_lane(lane) for lane in (2, 3))
    if args.diagnostic_lane:
        workers.extend(diagnostic_worker(lane) for lane in range(1,args.diagnostic_concurrency+1))
    elif set(args.models) & set(CONFIG_NAMES):
        workers.append(neutral_lane())
    await asyncio.gather(*workers)
    emit({'event': 'scheduler_finished', 'halted_all': halt_all.is_set(),
          'halted_models': [model for model in args.models if halted[model].is_set()],
          'recorded_api_cost': recorded_cost()})


if __name__ == '__main__':
    asyncio.run(main())
