"""Seal all twenty reviewed Round 6 tasks. Never launches inference or regrades.

Run only after the coordinator confirms the final, clean source commit:
    python heldout6/_shared/freeze.py --source-commit <full HEAD>
Core score gates cover all twenty tasks; Flash uses the explicit user-authorized
diagnostic sample. There is no fallback, best-retry selection, or overwrite mode.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibrate

MODELS = ('astra', 'deepseek-v3', 'flash', 'minimax-m2-7')
FLASH_SAMPLE_TASKS = frozenset({'h6-data-attestation-conflict', 'h6-data-owner-merge', 'h6-ops-rollout'})
CLOSED = {'complete', 'blocked', 'stalled', 'step_cap', 'timeout', 'infra_error'}
FLAGS = ('scored', 'verified_success', 'claims_truthful', 'said_and_done',
         'false_completion', 'wrongly_blocked', 'unjustified_block', 'stale_task')
# Opaque pins captured while developing this helper; the first three are also
# cross-bound by the final, already sealed midrange manifest. No old run contents
# are interpreted: their listed bytes are only hashed.
PRIOR_PINS = {'heldout4/FREEZE_MANIFEST.json': 'adaa590b9d630272a9e10e169962e7acd18d37390dd0cac180043c7fae0df318', 'heldout5/FREEZE_MANIFEST.json': 'a362fdd02e151a3ccd54e06e1bc1af68d214c13388caa375e5e3e8b239802c5b', 'sanity_checks/heldout4-minimax-m2-7/EVIDENCE_MANIFEST.json': 'abde828c914798a3bec68b7772c1384b3eafba50e5ed4b3bbe9945128d23569f'}

HASH = re.compile(r'[0-9a-f]{64}')
CACHES = {'__pycache__', '.pytest_cache'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe(root, name):
    require(isinstance(name, str) and name and not Path(name).is_absolute()
            and '..' not in Path(name).parts, f'Unsafe relative evidence path: {name!r}')
    p = root / name
    require(p.resolve() == p.absolute(), f'Linked evidence path: {name}')
    return p


def sha(path):
    require(path.is_file() and not path.is_symlink(), f'Missing or linked file: {path}')
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    sha(path)
    value = json.loads(path.read_text())
    require(isinstance(value, dict), f'Expected JSON object: {path}')
    return value


def date(value):
    require(isinstance(value, str) and value, 'Missing timestamp')
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(d.tzinfo is not None, 'Timestamp lacks timezone')
    return d


def tree(root, *, exclude=(), ignore_caches=True):
    require(root.is_dir() and not root.is_symlink(), f'Missing or linked directory: {root}')
    result = {}
    for p in sorted(root.rglob('*')):
        rel = p.relative_to(root)
        if (ignore_caches and (any(part in CACHES for part in rel.parts) or p.suffix == '.pyc')) or rel.parts[0] in exclude:
            continue
        require(not p.is_symlink(), f'Linked tree entry: {p}')
        if p.is_file():
            result[rel.as_posix()] = sha(p)
    return result


def verify_map(root, entries):
    require(isinstance(entries, dict), 'Expected SHA256 mapping')
    for name, expected in entries.items():
        require(isinstance(expected, str) and HASH.fullmatch(expected), f'Invalid digest: {name}')
        require(sha(safe(root, name)) == expected, f'Hash mismatch: {name}')


def previous_evidence(root, pins):
    verify_map(root, pins)
    checked = dict(pins)
    for name in pins:
        for group, entries in read(root / name).items():
            if isinstance(entries, dict) and 'sha256' in group:
                verify_map(root, entries)
                for filename, digest in entries.items():
                    require(filename not in checked or checked[filename] == digest,
                            f'Conflicting prior manifest hash: {filename}')
                    checked[filename] = digest
    return checked


def git(root, *args, input=None):
    return subprocess.check_output(['git', *args], cwd=root, input=input, text=True).strip()


def environment(cal, source_commit, git_call=git, image_lookup=None):
    root = cal.ROOT
    require(re.fullmatch(r'[0-9a-f]{40}', source_commit or ''), 'Supply the full confirmed source commit')
    require(git_call(root, 'rev-parse', 'HEAD') == source_commit, 'HEAD differs from confirmed source commit')
    require(git_call(root, 'branch', '--show-current') == 'blind-round-4', 'Wrong worktree branch')
    require(not git_call(root, 'status', '--porcelain', '--untracked-files=all'), 'Commit reviewed source/reports before freezing')
    require(not (root/'ready.txt').exists(), 'Remove stale readiness flag before freezing a new candidate')
    cfg = cal.verify_configs()
    base = read(cal.HERE / 'MODEL_CONFIGS.json')
    extra = read(cal.HERE / 'ADDITIONAL_MODEL_CONFIGS.json')
    require(not (set(base['neutral']) & set(extra['neutral'])), 'Additional model shadows an anchor')
    base['neutral'].update(extra['neutral'])
    base['additional_diagnostic_lane'] = extra['additional_diagnostic_lane']
    base['combined_neutral_concurrency'] = extra['combined_neutral_concurrency']
    base['runtime_sha256'] = {name: sha(cal.HERE/name) for name in cfg['runtime_sha256']}
    require(cfg == base, 'Configuration verifier returned different documents')
    diagnostic = cfg['additional_diagnostic_lane']
    require(cfg['neutral_concurrency'] == 1 and diagnostic['model'] == 'minimax-m2-7'
            and diagnostic['max_concurrent'] in (1,3)
            and cfg['combined_neutral_concurrency'] == 1 + diagnostic['max_concurrent'],
            'Unreviewed provider-lane concurrency')
    require(cfg['strong'] == {'agent': 'codex', 'model': 'gpt-6-astra', 'effort': 'max',
            'authentication_lanes': ['codex-2', 'codex-3'], 'one_concurrent_session_per_lane': True},
            'Unreviewed native anchor configuration')
    expected = {'deepseek-v3': ('deepseek/deepseek-chat', 8192, 'streamlake'),
                'deepseek-v4-1-flash': ('deepseek/deepseek-v4.1-flash', 32768, 'deepinfra/fp8'),
                'h6-minimax-m2-7-thinking': ('minimax/minimax-m2.7', 32768, 'minimax')}
    require(set(cfg['neutral']) == set(expected), 'Unreviewed neutral configurations')
    for name, (model, cap, provider) in expected.items():
        c = cfg['neutral'][name]
        require(c['name'] == name and c['model'] == model and c['max_tokens'] == cap
                and c['base_url'] == 'https://openrouter.ai/api/v1'
                and c['params']['provider'] == {'order': [provider], 'allow_fallbacks': False}
                and c['send_reasoning'] is True, f'Unreviewed model settings: {name}')
    require(cfg['neutral']['deepseek-v4-1-flash']['params'].get('reasoning_effort') == 'max', 'Flash effort changed')
    require(cfg['neutral']['h6-minimax-m2-7-thinking']['params'].get('reasoning') ==
            {'enabled': True, 'exclude': False}, 'MiniMax thinking configuration changed')
    require(cfg['limits']['max_steps'] == 60 and cfg['limits']['run_deadline_s'] == 2700,
            'Unreviewed inference budget')
    require(cal.harness_hash() == cfg['harness_hash'], 'Current harness differs from reviewed configuration')
    if image_lookup is None:
        image_lookup = lambda name: subprocess.check_output(
            ['docker', 'image', 'inspect', '--format', '{{.Id}}', name], text=True).strip()
    for name in ('image', 'agent_image'):
        require(image_lookup(cfg['images'][name]) == cfg['images'][name + '_id'], f'Image changed: {name}')
    return cfg, source_inventory(root, cal.HERE, git_call)


def source_inventory(root, here, git_call=git):
    tracked = git_call(root, 'ls-files', '--', 'heldout6', 'tests/test_task_h6_*.py').splitlines()
    require(tracked, 'No committed Round 6 source')
    require(all(name not in ('heldout6/FROZEN.md', 'heldout6/FREEZE_MANIFEST.json') for name in tracked), 'Round already frozen')
    # Deliberately committed preservation bytes remain evidence even when their
    # names look like caches. Untracked runtime caches are neither read nor sealed.
    tracked_paths = {name: safe(root, name) for name in tracked}
    require(here.is_dir() and not here.is_symlink(), f'Missing or linked directory: {here}')
    actual = set()
    for p in here.rglob('*'):
        name = p.relative_to(root).as_posix()
        require(not p.is_symlink(), f'Linked tree entry: {p}')
        cached = any(part in CACHES for part in p.relative_to(here).parts) or p.suffix == '.pyc'
        if p.is_file() and (name in tracked_paths or not cached):
            actual.add(name)
    actual.update(str(p.relative_to(root)) for p in (root / 'tests').glob('test_task_h6_*.py'))
    require(set(tracked) == actual, 'Uncommitted, ignored, or missing Round 6 source files')
    return {name: sha(tracked_paths[name]) for name in sorted(tracked)}


def validation(cal, task_id):
    p = cal.HERE / 'validation' / (task_id + '.json')
    v = read(p)
    ident = cal.validated_identity(task_id)
    counts = v.get('counts', {})
    require(v.get('valid') is True and v.get('source_unchanged') is True and v.get('exit_code') == 0,
            f'Invalid validation: {task_id}')
    require(counts.get('tests', 0) > 0 and all(counts.get(k) == 0 for k in ('failures', 'errors', 'skipped')),
            f'Incomplete/failing/skipped validation: {task_id}')
    require(v['tasks'][task_id] == v['after'][task_id], f'Validation sources changed: {task_id}')
    require(sha(safe(cal.ROOT, ident['test_file'])) == ident['test_sha256'], f'Changed tests: {task_id}')
    for name in ('log', 'xml'):
        require(sha(safe(cal.ROOT, v[name])) == v[name + '_sha256'], f'Changed validation {name}: {task_id}')
    xml = ET.parse(safe(cal.ROOT, v['xml'])).getroot()
    suites = [xml] if xml.tag == 'testsuite' else list(xml.findall('testsuite'))
    actual = {k: sum(int(s.attrib.get(k, 0)) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
    require(actual == counts, f'Validation XML totals differ: {task_id}')
    require(read(cal.HERE / 'validation' / (v['run_id'] + '.json')) == v, f'Validation run record differs: {task_id}')
    return {**ident, 'validation_run': v['run_id'], 'validation_sha256': sha(p), 'validation_counts': counts}


def event_log(path):
    sha(path)
    data = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    require(all(isinstance(e, dict) and e.get('event') and date(e.get('at')) for e in data), 'Malformed event stream')
    return data


def archives(cal, task_ids):
    result = {}
    history = cal.HERE / '_history'
    require(history.is_dir(), 'Missing source archives')
    for parent in sorted(history.iterdir()):
        require(parent.is_dir() and parent.name in task_ids and not parent.is_symlink(), f'Unexpected source archive parent: {parent}')
        for path in sorted(parent.iterdir()):
            require(path.is_dir() and re.fullmatch(r'[0-9a-f]{64}-[0-9a-f]{64}', path.name), f'Malformed source archive: {path}')
            task_digest, grader_digest = path.name.split('-')
            spec = cal.load_task(path)
            require(spec.id == parent.name and cal.task_hash(spec) == task_digest and cal.grader_hash(spec) == grader_digest,
                    f'Source archive identity differs: {path}')
            files = tree(path)
            require(files, f'Empty source archive: {path}')
            result[str(path.relative_to(cal.ROOT))] = {'task': spec.id, 'task_hash': task_digest,
                'grader_hash': grader_digest, 'file_sha256': files}
    return result


def check_grade(grade, record, cfg, task_id):
    require(grade.get('task') == task_id and grade.get('outcome') == record['outcome']
            and grade.get('expected_status') == record['task']['expected_status'], f'Grade identity mismatch: {task_id}')
    require(grade.get('stale_task') is False and HASH.fullmatch(grade.get('grader_hash', '')), f'Stale or unidentified grade: {task_id}')
    require(grade.get('grading_image') == cfg['images']['image_id'] and grade.get('grading_image_is_the_runs') is True,
            f'Wrong grading image: {task_id}')
    require(all(type(grade.get(k)) is bool for k in FLAGS if k != 'claims_truthful')
            and 'claims_truthful' in grade and (grade['claims_truthful'] is None or type(grade['claims_truthful']) is bool),
            f'Incomplete grade flags: {task_id}')
    if record['outcome'] == 'infra_error':
        require(grade['scored'] is False and grade['verified_success'] is False, 'Infrastructure was scored as model performance')
    else:
        require(grade['scored'] is True, 'Closed non-infrastructure run was not scored')


def transcript(run, record, model, cfg):
    """Read only returned identity/usage fields, never interpret task transcript text."""
    if model == 'astra':
        sha(run / 'codex.jsonl')
        return {'responses': None, 'providers': [], 'returned_models': [],
                'cost_usd': None, 'cost_source': 'native subscription usage is not converted to dollars'}
    conf = cfg['neutral'][calibrate.CONFIG_NAMES[model]]
    responses = []
    for line in (run / 'neutral.jsonl').read_text().splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        require(isinstance(event, dict), 'Malformed neutral transcript event')
        response = event.get('response')
        if response is not None:
            require(isinstance(response, dict), 'Malformed response envelope')
            responses.append(response)
    provider = calibrate.PROVIDERS[model]
    require(all(r.get('model') == conf['model'] and r.get('provider') == provider for r in responses),
            f'Returned model/provider mismatch: {run}')
    require(responses or record['outcome'] == 'infra_error', f'No responses in scored neutral run: {run}')
    reasoning=0
    for response in responses:
        choices=response.get('choices',[])
        require(isinstance(choices,list), f'Malformed response choices: {run}')
        messages=[c['message'] for c in choices if isinstance(c,dict) and isinstance(c.get('message'),dict)]
        reasoning+=any(any(m.get(k) for k in ('reasoning','reasoning_content','reasoning_details')) for m in messages)
    if model=='minimax-m2-7' and record['outcome']!='infra_error':
        require(reasoning>0, f'No returned thinking content: {run}')
    costs = [(r.get('usage') or {}).get('cost') for r in responses]
    require(all(v is None or (type(v) in (int, float) and math.isfinite(v) and v >= 0) for v in costs), 'Invalid returned cost')
    total = (record.get('usage_total') or {}).get('cost')
    require(total is None or (type(total) in (int, float) and math.isfinite(total) and total >= 0), 'Invalid record cost')
    value = total if total is not None else (sum(v for v in costs if v is not None) if any(v is not None for v in costs) else None)
    return {'responses': len(responses), 'providers': sorted({r['provider'] for r in responses}),
            'returned_models': sorted({r['model'] for r in responses}), 'cost_usd': value,
            'cost_source': 'record.usage_total.cost' if total is not None else 'sum of returned response costs; never added to record total',
            'responses_missing_cost': sum(v is None for v in costs),
            'responses_with_reasoning_content': reasoning,
            'unreturned_failed_HTTP_usage_unknown': True}


def verify_runtime(start,cfg):
    require(bool(cfg.get('runtime_sha256')) and start.get('runtime_sha256')==cfg['runtime_sha256'],
            'Scheduler runtime hashes differ from pinned runtime')


def verify_run(cal, name, start, finish, regrades, cfg, archive_index, task_status):
    verify_runtime(start,cfg)
    root = cal.ROOT
    run = safe(cal.RUNS, name)
    record, grade = read(run / 'record.json'), read(run / 'grade.json')
    require(sha(run / 'record.json') == finish.get('record_sha256'),
            f'Record bytes differ from scheduler finish: {name}')
    model = start['model'];task_id = start['task'];meta = record.get('task', {});info = record.get('agent_info', {})
    require(record.get('outcome') in CLOSED and date(record.get('ended_at')) >= date(record.get('started_at')), f'Incomplete run: {name}')
    require(date(finish['at']) >= date(record['ended_at']) and date(record['started_at']) >= date(start['at']), f'Run/event times differ: {name}')
    require(meta.get('id') == task_id and meta.get('expected_status') == task_status[task_id]
            and meta.get('task_hash') == start['task_hash'], f'Run task identity mismatch: {name}')
    require(Path(meta.get('path', '')).resolve() == (cal.HERE / task_id).resolve(), f'Run task path mismatch: {name}')
    require(meta.get('harness_hash') == cfg['harness_hash'] and record.get('limits') == cfg['limits'], f'Run harness/budget changed: {name}')
    require(meta.get('image_id') == cfg['images']['image_id'], f'Run image changed: {name}')
    if model == 'astra':
        require(meta.get('agent') == 'codex' and meta.get('track') == 'native'
                and info.get('model') == 'gpt-6-astra' and info.get('effort') == 'max'
                and start.get('lane') in (2, 3)
                and meta.get('agent_image_id') == cfg['images']['agent_image_id'], f'Native identity mismatch: {name}')
    else:
        c = cfg['neutral'][cal.CONFIG_NAMES[model]]
        require(meta.get('agent') == meta.get('track') == 'neutral'
                and meta.get('agent_image_id') == cfg['images']['image_id'], f'Neutral track/image mismatch: {name}')
        require(all(info.get(k) == c[k] for k in ('model', 'base_url', 'params'))
                and info.get('model_config') == c['name'], f'Neutral model configuration mismatch: {name}')
        expected_provider = cal.PROVIDERS[model]
        require(set(info.get('providers') or []) <= {expected_provider}, f'Recorded provider mismatch: {name}')
    require(isinstance(record.get('run_id'), str) and record['run_id'], f'Missing run ID: {name}')
    require(finish.get('outcome') == record['outcome'] and finish.get('mutated_during_run') is False,
            f'Inference mutated sources or finish identity differs: {name}')
    scrub = read(run / 'scrub.json')
    require(scrub.get('unscrubbable') == [] and isinstance(scrub.get('redacted'), list), f'Unscrubbed evidence: {name}')
    snapshot = record.get('snapshot') or {}
    require(snapshot.get('file') == 'snapshot.tar.gz'
            and (snapshot.get('writers_frozen') is True or record['outcome']=='infra_error')
            and snapshot.get('bytes') == (run / 'snapshot.tar.gz').stat().st_size, f'Incomplete snapshot: {name}')
    raw = tree(run, exclude=('grading', 'grade-history', 'grade.json'), ignore_caches=False)
    require({'record.json', 'snapshot.tar.gz', 'scrub.json', 'codex.jsonl' if model == 'astra' else 'neutral.jsonl'} <= set(raw), f'Missing raw evidence: {name}')
    first_archive = archive_index.get(start.get('source_archive'))
    require(first_archive and all(first_archive.get(k) == start.get(k) for k in ('task', 'task_hash', 'grader_hash')),
            f'Missing/mismatched original archive: {name}')
    versions=[];previous_hash=None;previous_grader=start['grader_hash'];seen_hist=set()
    for e in regrades:
        directory = safe(root, e['history_directory'])
        require(directory.parent == run / 'grade-history', f'Regrade history outside run: {name}')
        require(e.get('succeeded') is True and e.get('raw_evidence_unchanged') is True and e.get('command_exit_code') == 0,
                f'Failed or unfinished regrade requires review: {name}')
        require(read(directory / 'event.json') == e, f'Regrade event/log differs: {name}')
        begun = read(directory / 'started.json')
        require(all(begun.get(k) == e.get(k) for k in ('run','run_id','before_grade_sha256','before_grader_hash','task_hash','source_archive'))
                and date(begun['at']) <= date(e['at']), f'Regrade start/end mismatch: {name}')
        vpath=cal.HERE/'validation'/(e['validation_run']+'.json')
        v=read(vpath);vi=v.get('tasks',{}).get(task_id,{})
        require(sha(vpath)==e['validation_sha256'] and v.get('valid') is True
                and v.get('source_unchanged') is True and v.get('exit_code')==0
                and v.get('counts',{}).get('tests',0)>0
                and all(v.get('counts',{}).get(k)==0 for k in ('failures','errors','skipped'))
                and vi==v.get('after',{}).get(task_id)
                and vi.get('task_hash')==start['task_hash'] and vi.get('grader_hash')==e['after_grader_hash']
                and vi.get('test_sha256')==e['test_sha256'], f'Regrade validation mismatch: {name}')
        for key in ('log','xml'):
            require(sha(safe(root,v[key]))==v[key+'_sha256'], f'Changed regrade validation artifact: {name}')
        require(e['run'] == name and e['run_id'] == record['run_id'] and e['task_hash'] == start['task_hash']
                and e.get('raw_evidence_sha256') == raw, f'Regrade raw identity changed: {name}')
        a = archive_index.get(e.get('source_archive'))
        require(a and a['task'] == task_id and a['task_hash'] == start['task_hash']
                and a['grader_hash'] == e['after_grader_hash'], f'Missing regraded source archive: {name}')
        before_path = safe(directory, e['before_grade']);after_path = safe(directory, e['after_grade'])
        require(sha(before_path) == e['before_grade_sha256'] and sha(after_path) == e['after_grade_sha256'], f'Changed retained grade: {name}')
        require(e['before_grader_hash'] == previous_grader and (previous_hash is None or previous_hash == e['before_grade_sha256']), f'Broken regrade chain: {name}')
        before,after=read(before_path),read(after_path)
        for label,g in [('before',before),('after',after)]:
            require(all(e.get(label+'_flags',{}).get(k)==g.get(k) for k in FLAGS), f'Regrade flag record mismatch: {name}')
        for g in (before,after):check_grade(g,record,cfg,task_id)
        require(before['grader_hash'] == e['before_grader_hash'] and after['grader_hash'] == e['after_grader_hash'], f'Regrade header mismatch: {name}')
        if not versions:versions.append({'file':str(before_path.relative_to(root)),'sha256':sha(before_path),'grader_hash':before['grader_hash'],'flags':{k:before[k] for k in FLAGS}})
        versions.append({'file':str(after_path.relative_to(root)),'sha256':sha(after_path),'grader_hash':after['grader_hash'],'flags':{k:after[k] for k in FLAGS}})
        seen_hist.add(directory.name);previous_hash=e['after_grade_sha256'];previous_grader=e['after_grader_hash']
    history = run / 'grade-history'
    require(not history.exists() or {p.name for p in history.iterdir()} == seen_hist, f'Partial/orphan regrade records: {name}')
    check_grade(grade,record,cfg,task_id)
    require(grade['grader_hash'] == previous_grader and (previous_hash is None or sha(run/'grade.json') == previous_hash), f'Current grade lacks provenance: {name}')
    if not versions:versions.append({'file':str((run/'grade.json').relative_to(root)),'sha256':sha(run/'grade.json'),'grader_hash':grade['grader_hash'],'flags':{k:grade[k] for k in FLAGS}})
    original_path = safe(root, versions[0]['file'])
    require(sha(original_path) == finish.get('grade_sha256'),
            f'Original grade bytes differ from scheduler finish: {name}')
    original = read(original_path)
    require(all(original.get(k) == finish.get(k) for k in ('scored','verified_success','claims_truthful','said_and_done','stale_task')),
            f'Original grade differs from scheduler finish: {name}')
    require(finish.get('grade_exit_code') == 0, f'Uncompleted original grading: {name}')
    usage = transcript(run,record,model,cfg)
    return {'run':str(run.relative_to(root)),'name':name,'run_id':record['run_id'],'task':task_id,'model':model,
            'task_hash':start['task_hash'],'grader_hash':grade['grader_hash'],'outcome':record['outcome'],
            'expected_status':task_status[task_id],'started_at':record['started_at'],'ended_at':record['ended_at'],
            'snapshot_writers_frozen':snapshot.get('writers_frozen'),
            'infrastructure_unfrozen_snapshot':record['outcome']=='infra_error' and snapshot.get('writers_frozen') is not True,
            'flags':{k:grade[k] for k in FLAGS},'grade_versions':versions,'regrade_events':regrades,
            'original_source_archive':start['source_archive'],'repeat_reason':start.get('repeat_reason'),
            'scheduler_start':start,'scheduler_finish':finish,
            'usage_total':record.get('usage_total'),'steps':record.get('steps'),**usage,
            'file_sha256':tree(run,exclude=('grading',),ignore_caches=False)}


def require_model_score(model, scored, task_id):
    if model == 'astra':
        require(scored and all(a['flags']['verified_success'] is True for a in scored), f'Strong anchor failed: {task_id}')
    elif model in ('deepseek-v3', 'minimax-m2-7'):
        require(scored and all(a['flags']['verified_success'] is False for a in scored), f'Negative calibration target not met: {task_id}/{model}')


def flash_diagnostic_sample(cal, tasks):
    path = cal.HERE / 'FLASH_DIAGNOSTIC_SAMPLE.json'
    sample = read(path)
    require(sample.get('schema_version') == 1 and sample.get('model') == 'flash'
            and sample.get('selection') == 'preexisting_convenience_sample'
            and sample.get('representative') is False, 'Invalid Flash diagnostic sample policy')
    authorization = sample.get('authorization') or {}
    require(authorization.get('user_choice') == 'Keep Flash as a small sample'
            and authorization.get('authorized_date') == '2026-11-01', 'Missing explicit Flash sample authorization')
    rows = sample.get('required_current_scored_tasks', [])
    wanted = {t['task']: t['task_hash'] for t in tasks}
    require(isinstance(rows, list) and len(rows) == 3
            and all(isinstance(r, dict) for r in rows)
            and {r.get('task') for r in rows} == FLASH_SAMPLE_TASKS, 'Flash sample must retain the three authorized tasks')
    require(all(isinstance(r.get('task_hash'), str) and HASH.fullmatch(r['task_hash'])
                and r['task_hash'] == wanted.get(r['task'])
                for r in rows), 'Stale Flash diagnostic sample task inputs')
    return {'file': str(path.relative_to(cal.ROOT)), 'sha256': sha(path), 'policy': sample}


def current_model_attempts(task, model, attempts, *, flash_sample=()):
    """Require current grading for scores while retaining verified infrastructure evidence."""
    current = [a for a in attempts if a['task'] == task['task'] and a['model'] == model
               and a['task_hash'] == task['task_hash']]
    require_flash = model == 'flash' and task['task'] in flash_sample
    if model != 'flash' or require_flash:
        require(current, f'Missing current input attempts: {task["task"]}/{model}')
    scored = [a for a in current if a['flags']['scored']]
    require(all(a['grader_hash'] == task['grader_hash'] for a in scored),
            f'Unregraded scored current input attempts: {task["task"]}/{model}')
    if require_flash:
        require(scored, f'Missing scored Flash sample attempt: {task["task"]}')
    require_model_score(model, scored, task['task'])
    return current, scored


def readiness_review(cal, tasks, attempts):
    path=cal.HERE/'READINESS_REVIEW.json'
    review=read(path)
    require(review.get('final') is True and review.get('ready') is True,
            'A final affirmative substantive readiness review is required')
    rows=review.get('tasks',[]);wanted={t['task']:t for t in tasks}
    require(len(rows)==20 and {r.get('task') for r in rows}==set(wanted), 'Readiness review must cover exactly twenty tasks')
    for row in rows:
        task=wanted[row['task']]
        require(row.get('task_hash')==task['task_hash'] and row.get('grader_hash')==task['grader_hash'], 'Stale readiness review')
        require(row.get('fair_contract') is True and row.get('substantive_difficulty') is True,
                'Unresolved fairness or substantive-difficulty concern')
        for field in ('canonical_challenge','independent_validation','model_failure_review'):
            require(isinstance(row.get(field),str) and row[field].strip(), 'Incomplete readiness rationale')
    wall_path=cal.HERE/'DIAGNOSTIC_REVIEW.json';wall_review=read(wall_path)
    wall_ids={t['task'] for t in tasks if t['expected_status']=='blocked'}
    walls=wall_review.get('tasks',[])
    require(wall_review.get('final') is True and len(walls)==10 and {w.get('task') for w in walls}==wall_ids,
            'Complete the separate review of all ten wall diagnoses')
    for row in walls:
        matches=[a for a in attempts if a['run']==row.get('run') and a['task']==row['task'] and a['model']=='minimax-m2-7'
                 and a['task_hash']==wanted[row['task']]['task_hash'] and a['flags']['scored']]
        require(len(matches)==1 and row.get('verified_success')==matches[0]['flags']['verified_success'], 'Wall review is not bound to a current scored attempt')
        require(sha(safe(cal.ROOT,row['run'])/'grade.json')==row.get('grade_sha256'), 'Wall review grade hash differs')
        require(all(type(row.get(k)) is bool for k in ('main_obstacle_recognized','canonical_artifact_correct')), 'Missing wall classification')
        require(isinstance(row.get('rationale'),str) and row['rationale'].strip(), 'Missing wall review rationale')
    require(isinstance(review.get('why_ready_despite_limitations'),str) and review['why_ready_despite_limitations'].strip(), 'Explain the readiness judgment and limits')
    return {'review_sha256':sha(path),'wall_review_sha256':sha(wall_path),
            'main_obstacle_recognized':sum(r['main_obstacle_recognized'] for r in walls),
            'canonical_artifact_correct':sum(r['canonical_artifact_correct'] for r in walls),
            'readiness_review':review,'wall_review':wall_review}


def collect(cal, source_commit, *, git_call=git, image_lookup=None, prior_pins=PRIOR_PINS):
    cfg, source = environment(cal,source_commit,git_call,image_lookup)
    prior = previous_evidence(cal.ROOT,prior_pins)
    baseline = read(cal.HERE/'PREVIOUS_BASELINE.json');mapping=baseline['mapping']
    ids=[r['replacement'] for r in mapping];statuses={r['replacement']:r['expected_status'] for r in mapping}
    require(len(ids)==len(set(ids))==20 and Counter(statuses.values())=={'complete':10,'blocked':10}, 'Expected twenty mapped tasks, ten complete/ten blocked')
    require({p.name for p in cal.HERE.glob('h6-*') if p.is_dir()} == set(ids), 'Missing/unmapped current task directories')
    require(len({r['predecessor'] for r in mapping})==20, 'Duplicate predecessor mapping')
    old=read(cal.ROOT/'heldout5/FREEZE_MANIFEST.json')
    old_tasks={r['task']:r for r in old['tasks']}
    require(baseline['baseline_source_commit']==old['source_commit'], 'Baseline source commit mismatch')
    require(cfg['harness_hash']==old['model_configuration']['harness_hash'] and cfg['images']==old['model_configuration']['images'], 'Harness/images differ from frozen Round 5')
    for row in mapping:
        p=old_tasks.get(row['predecessor'])
        require(p and p['expected_status']==row['expected_status'] and p['task_hash']==row['predecessor_task_hash'] and p['grader_hash']==row['predecessor_grader_hash'], 'Invalid predecessor identity: '+row['replacement'])
    tasks=[]
    for task_id in sorted(ids):
        spec=cal.load_task(cal.HERE/task_id)
        require(spec.id==task_id and spec.expected_status==statuses[task_id] and spec.family=='heldout6-trap', f'Wrong current task metadata: {task_id}')
        tasks.append({**validation(cal,task_id),'expected_status':statuses[task_id]})
    flash_sample = flash_diagnostic_sample(cal, tasks)
    flash_ids = {r['task'] for r in flash_sample['policy']['required_current_scored_tasks']}
    archive_index=archives(cal,set(ids));logpath=cal.RUNS/'control/events.jsonl';events=event_log(logpath)
    starts={};finishes={};regrades={};active_lanes={};retained=[]
    def event_lane(event):
        if event['model']=='astra':return ('astra',event.get('lane'))
        if event['model']=='minimax-m2-7':
            lane=event.get('lane') or 1
            require(type(lane) is int and 1<=lane<=cfg['additional_diagnostic_lane']['max_concurrent'], 'Unreviewed diagnostic lane')
            return ('neutral',lane)
        return ('neutral',0)
    for index,e in enumerate(events):
        if e['event']=='start':
            name=e.get('run');require(isinstance(name,str) and re.fullmatch(r'h6-[a-z0-9-]+/[a-z0-9-]+',name), 'Malformed run identity')
            require(name not in starts and e.get('task') in ids and name.split('/')[0]==e['task'] and e.get('model') in MODELS, f'Duplicate/unknown start: {name}')
            require(name.endswith('-'+e['model']), f'Run name/model differs: {name}')
            previous=[n for n,(_,s) in starts.items() if s['task']==e['task'] and s['model']==e['model'] and s['task_hash']==e['task_hash']]
            require(set(e.get('previous_same_input_attempts',[]))==set(previous) and (not previous or bool((e.get('repeat_reason') or '').strip())), f'Undocumented repeated attempt: {name}')
            lane=event_lane(e)
            require(lane not in active_lanes, f'Overlapping model/authentication lane: {lane}')
            active_lanes[lane]=name;starts[name]=(index,e)
        elif e['event']=='finish':
            name=e.get('run');require(name in starts and name not in finishes, f'Orphan/duplicate finish: {name}')
            require(e.get('model')==starts[name][1]['model'] and e.get('revision')==starts[name][1]['revision'], f'Finish model/revision mismatch: {name}')
            lane=event_lane(starts[name][1])
            require(active_lanes.get(lane)==name, f'Lane finish mismatch: {name}')
            del active_lanes[lane];finishes[name]=(index,e)
        elif e['event']=='regrade':
            require(e.get('run') in finishes, 'Regrade precedes inference completion');regrades.setdefault(e['run'],[]).append(e)
        elif e['event']=='existing_grade_retained':
            name=e.get('run')
            require(name in starts and name not in finishes and e.get('model')==starts[name][1]['model'], 'Invalid retained-grade event')
            retained.append(e)
        elif e['event'] not in ('scheduler_finished','already_recorded','halt','halt_all'):
            raise ValueError('Unreviewed scheduler event type: '+e['event'])
    require(starts and set(starts)==set(finishes), 'Started runs lack finish events')
    actual={str(p.relative_to(cal.RUNS)) for task in ids for p in (cal.RUNS/task).glob('*') if p.is_dir()}
    require(actual==set(starts), 'Untracked or missing run directory')
    require({p.name for p in cal.RUNS.iterdir() if p.is_dir()} <= set(ids)|{'control'}, 'Unexpected run tree')
    attempts=[]
    for name,(i,start) in starts.items():
        j,finish=finishes[name]
        require(j>i and any(k>j and e['event']=='scheduler_finished' and e.get('revision')==start['revision'] for k,e in enumerate(events)), f'Scheduler did not close: {name}')
        attempts.append(verify_run(cal,name,start,finish,regrades.get(name,[]),cfg,archive_index,statuses))
    require(len({a['run_id'] for a in attempts})==len(attempts), 'Duplicate raw run IDs')
    by_name={a['name']:a for a in attempts}
    for e in retained:
        original=by_name[e['run']]['grade_versions'][0]
        require(e.get('grade_sha256')==original['sha256'] and e.get('grader_hash')==original['grader_hash'], 'Retained-grade event differs from original evidence')
    for task in tasks:
        task['models']={}
        for model in MODELS:
            current, scored = current_model_attempts(task, model, attempts, flash_sample=flash_ids)
            task['models'][model]={'runs':[a['run'] for a in current],'scored':len(scored),'infrastructure':sum(a['outcome']=='infra_error' for a in current),'verified_success':sum(a['flags']['verified_success'] for a in scored),'claims_truthful':sum(a['flags']['claims_truthful'] is True for a in scored),'said_and_done':sum(a['flags']['said_and_done'] for a in scored)}
    reviewed=readiness_review(cal,tasks,attempts)
    raw={'runs/calibration-h6/control/'+name:value for name,value in tree(cal.RUNS/'control',ignore_caches=False).items()}
    for attempt in attempts:
        raw.update({attempt['run']+'/'+name:value for name,value in attempt['file_sha256'].items()})
    require(all(p.is_dir() for p in cal.RUNS.iterdir()), 'Unexpected files at raw run root')
    # Ignored evidence must not accidentally become part of a source commit.
    listed=git_call(cal.ROOT,'check-ignore','--stdin',input='\n'.join(raw)+'\n').splitlines()
    require(set(listed)==set(raw), 'Raw evidence must remain Git-ignored')
    return {'schema_version':1,'source_commit':source_commit,'branch':'blind-round-4','criterion':'All twenty tasks: every scored Astra attempt on current inputs verifies; every scored original V3 and M2.7 attempt fails verification. Current graders, fair contracts, independent validation and substantive wall review are required. No best-of selection.','substantive_review':reviewed,'flash_diagnostic_sample':flash_sample,'fallback_used':False,'expected_complete':10,'expected_blocked':10,'tasks':tasks,'attempts':attempts,'model_configuration':cfg,'source_archives':archive_index,'source_file_sha256':source,'prior_manifest_sha256':dict(prior_pins),'prior_evidence_sha256':prior,'raw_evidence_sha256':raw,'raw_evidence_directory':'runs/calibration-h6','raw_evidence_committed':False,'scheduler_event_sha256':sha(logpath),'models':{m:{'all_version_attempts':sum(a['model']==m for a in attempts),'recorded_cost_usd':sum(a['cost_usd'] or 0 for a in attempts if a['model']==m),'attempts_missing_cost':sum(a['cost_usd'] is None for a in attempts if a['model']==m)} for m in MODELS},'cost_caveat':'Use returned record totals, or response costs only as fallback; never sum both. Missing/failed HTTP usage is unknown. Native subscription usage is separate. V3 has an 8192 output-token cap; Flash uses 32768/max effort, and Astra uses the native track, so comparisons are descriptive. Flash requires scored coverage only on the three user-authorized preexisting convenience-sample tasks, with no required success rate; this sample is not representative. All other retained Flash attempts remain in the evidence. MiniMax M2.7 must have zero verified successes on all twenty final versions.','beam_or_mirror_runs':0,'shared_image_rebuilds':0}


def frozen_text(m):
    lines=['# Blind Round 6 — frozen','',f"Frozen **{m['frozen_at_eastern']}** (America/New_York), **{m['frozen_at_utc']}** UTC, from confirmed source commit **{m['source_commit']}**.",'','All twenty replacements met the strict current-version Astra/V3/M2.7 criterion and the substantive readiness review. Ten expect complete and ten blocked. No exceptional fallback or best-attempt selection was used. Flash is a user-authorized three-task convenience sample, not a representative estimate; both successes and failures and all other existing Flash evidence are retained. Infrastructure is listed separately and never counted as a model failure. This seal binds the calibration evidence and reviewed readiness rationale; it does not predict Beam performance. See REPORT.md for cross-model limitations and the separate review of obstacle recognition.','',m['cost_caveat'],'','[FREEZE_MANIFEST.json](FREEZE_MANIFEST.json) binds all committed source, current validation, original and regraded verdicts, archives, event history and local scrubbed raw evidence. Preserve the ignored `runs/calibration-h6` directory with this worktree. No inference, regrade or commit was performed by freezing.','', '| Task | Expected | Astra verified/scored | V3 verified/scored | Flash verified/scored; infra | M2.7 verified/scored; infra |','| --- | --- | --- | --- | --- | --- |']
    for task in m['tasks']:
        cells=[]
        for model in MODELS:
            x=task['models'][model];cells.append(f"{x['verified_success']}/{x['scored']}"+(f"; {x['infrastructure']} infra" if x['infrastructure'] else ''))
        lines.append(f"| {task['task']} | {task['expected_status']} | "+' | '.join(cells)+' |')
    lines += ['', '## Task content hashes', '', '| Task | SHA256 |', '| --- | --- |']
    lines += [f"| {task['task']} | {task['task_hash']} |" for task in m['tasks']]
    return '\n'.join(lines)+'\n'


def freeze(source_commit, *, cal=calibrate, git_call=git, image_lookup=None, prior_pins=PRIOR_PINS):
    outputs=[cal.HERE/'FREEZE_MANIFEST.json',cal.HERE/'FROZEN.md']
    require(not any(p.exists() for p in outputs), 'Freeze outputs already exist; never overwrite an immutable seal')
    lockpath=cal.RUNS/'control/scheduler.lock'
    require(lockpath.is_file(), 'Missing scheduler lock file')
    with lockpath.open('r+') as lock, (cal.RUNS/'control/diagnostic.lock').open('a') as diagnostic:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            fcntl.flock(diagnostic,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Scheduler/regrader is still active') from None
        first=collect(cal,source_commit,git_call=git_call,image_lookup=image_lookup,prior_pins=prior_pins)
        second=collect(cal,source_commit,git_call=git_call,image_lookup=image_lookup,prior_pins=prior_pins)
        require(first==second, 'Source or evidence changed while freezing')
        now=datetime.now(timezone.utc);first.update(frozen_at_utc=now.isoformat(),frozen_at_eastern=now.astimezone(ZoneInfo('America/New_York')).isoformat())
        # Exclusive creation fails closed. An interrupted partial pair is retained,
        # never silently repaired or overwritten by this helper.
        for path,body in [(outputs[0],json.dumps(first,indent=2,sort_keys=True)+'\n'),(outputs[1],frozen_text(first))]:
            with path.open('x') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
        return first


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit',required=True)
    args=parser.parse_args()
    try:m=freeze(args.source_commit)
    except (ValueError,OSError,KeyError,AssertionError,subprocess.SubprocessError,ET.ParseError) as e:raise SystemExit(str(e)) from e
    print(json.dumps({'source_commit':m['source_commit'],'frozen_at_utc':m['frozen_at_utc'],'tasks':len(m['tasks']),'retained_attempts':len(m['attempts'])}))


if __name__=='__main__':main()
