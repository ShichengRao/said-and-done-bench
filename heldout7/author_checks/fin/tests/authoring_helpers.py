"""Shared author-side helpers: materialize reference solutions and grade them.

This is NOT the benchmark harness. It reproduces only what the supplied
author_support files define: the setup.sh workspace build, the shared
_review.assess entry point and a bound post-run author review. The coordinator's
Docker integration (real /run/record.json, /grader mounts, agent runs) is not run.
"""
import datetime
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'author_support'))
import task_api  # noqa: E402

GENERATED = ('__pycache__', '.pytest_cache', '*.pyc')


def task_dir(task_id):
    return ROOT / 'deliverables' / task_id


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def solutions(task_id):
    base = task_dir(task_id) / 'solutions'
    return sorted(p.name for p in base.iterdir() if (p / 'expect.json').is_file())


def materialize(task_id, solution, dest):
    """Build the run workspace like prepare_workspace, then apply a reference solution."""
    task = task_dir(task_id); dest = Path(dest)
    shutil.copytree(task / 'workspace', dest, ignore=shutil.ignore_patterns(*GENERATED))
    setup = subprocess.run(['bash', str(task / 'setup' / 'setup.sh')], cwd=dest, capture_output=True, text=True, timeout=60)
    assert setup.returncode == 0, setup.stdout + setup.stderr
    folder = task / 'solutions' / solution
    if (folder / 'files').is_dir():
        shutil.copytree(folder / 'files', dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*GENERATED))
    run = None
    if (folder / 'run.sh').is_file():
        run = subprocess.run(['bash', str(folder / 'run.sh')], cwd=dest, capture_output=True, text=True, timeout=300)
    return run


def pinned_hash(task_id):
    return task_api.task_hash(task_api.load_task(task_dir(task_id)))


def grade(task_id, workspace, scratch, *, outcome, claims, decisions=None):
    """Run the shared assess() exactly as grade.py would, with a bound review if supplied."""
    task = task_dir(task_id); grader = task / 'grader'; scratch = Path(scratch); scratch.mkdir(parents=True, exist_ok=True)
    review_module = load_module(grader / '_review.py', '_author_review_' + task_id.replace('-', '_'))
    checks = load_module(grader / 'task_checks.py', '_author_checks_' + task_id.replace('-', '_'))
    config = json.loads((grader / 'review_config.json').read_text())
    record = {'task': {'id': task_id, 'task_hash': config['task_hash']}, 'outcome': outcome,
              'submit': {'status': outcome, 'claims': claims}}
    record_path = scratch / 'record.json'; record_path.write_text(json.dumps(record))
    review_path = scratch / 'monitor' / 'offline_review' / 'semantic.json'
    if decisions is not None:
        binding = review_module.binding(record_path, workspace, grader, config)
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text(json.dumps({
            'schema_version': 1, 'provenance': 'post_run_author_adjudication', 'final': True, 'binding': binding,
            'reviewer': 'task author (reference adjudication)', 'reviewed_at': datetime.date(2026, 11, 2).isoformat(),
            'rationale': 'Reference response adjudicated against author_only/ground_truth.json.',
            'evidence': ['solutions reference response'], 'decisions': decisions}))
    return review_module.assess(record_path=record_path, workspace=Path(workspace), grader=grader,
                                review_path=review_path, task_check=checks.check_workspace)


def tree_digest(root):
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob('*')):
        rel = p.relative_to(root)
        if any(part in ('__pycache__', '.pytest_cache') for part in rel.parts) or p.suffix == '.pyc' or not p.is_file():
            continue
        h.update(str(rel).encode() + b'\0' + p.read_bytes() + b'\0')
    return h.hexdigest()


FORBIDDEN_PUBLIC = ('blocked', 'blocker', 'feasib', 'submit --status', 'owner_review', 'pushback')


def package_problems(task_id):
    """Static package requirements from CLAUDE.md."""
    import tomllib
    task = task_dir(task_id); problems = []
    for name in ('task.toml', 'goal.md', 'workspace', 'setup/setup.sh', 'grader/grade.py', 'grader/_review.py',
                 'grader/task_checks.py', 'grader/original', 'grader/review_config.json', 'solutions', 'AUTHOR_PROOF.md',
                 'author_only/ground_truth.json'):
        if not (task / name).exists():
            problems.append('missing ' + name)
    meta = tomllib.loads((task / 'task.toml').read_text())
    want = {'id': task_id, 'family': 'heldout7-delivery', 'tracks': ['neutral', 'native'], 'command_timeout_s': 120}
    problems += ['task.toml %s=%r' % (k, meta.get(k)) for k, v in want.items() if meta.get(k) != v]
    if set(meta.get('claims', {})) != {'files_changed'}:
        problems.append('claims must be files_changed only')
    if (task / 'grader/grade.py').read_bytes() != (ROOT / 'author_support/grade_entry.py').read_bytes():
        problems.append('grade.py differs from shared entry')
    if (task / 'grader/_review.py').read_bytes() != (ROOT / 'author_support/review_grader.py').read_bytes():
        problems.append('_review.py differs from shared review grader')
    if tree_digest(task / 'workspace') != tree_digest(task / 'grader/original'):
        problems.append('grader/original differs from workspace')
    config = json.loads((task / 'grader/review_config.json').read_text())
    if config != {'task_id': task_id, 'expected_status': meta['expected_status'], 'task_hash': pinned_hash(task_id)}:
        problems.append('review_config not pinned to current task inputs')
    truth = json.loads((task / 'author_only/ground_truth.json').read_text())
    if truth.get('expected_status') != meta['expected_status']:
        problems.append('ground truth status differs')
    public = [task / 'goal.md'] + [p for p in (task / 'workspace').rglob('*') if p.is_file()]
    for path in public:
        text = path.read_text(errors='ignore').lower()
        for word in FORBIDDEN_PUBLIC:
            if word in text:
                problems.append('public file %s mentions %r' % (path.relative_to(task), word))
    return problems


def check_solution(task_id, solution, tmp_path):
    """Materialize a reference solution, grade it, and compare with its expect.json."""
    task = task_dir(task_id); spec = json.loads((task / 'solutions' / solution / 'expect.json').read_text())
    workspace = Path(tmp_path) / 'workspace'
    run = materialize(task_id, solution, workspace)
    result = grade(task_id, workspace, Path(tmp_path) / 'run', outcome=spec['outcome'], claims=spec['claims'], decisions=spec.get('decisions'))
    expect = spec['expect']; problems = []
    if 'run_ok' in expect and (run is None or (run.returncode == 0) != expect['run_ok']):
        problems.append('run.sh result %r' % (run and (run.returncode, run.stdout[-500:], run.stderr[-500:])))
    if 'safe_partial' in expect and result['safe_partial'] != expect['safe_partial']:
        problems.append('safe_partial %r' % result['safe_partial'])
    if 'violations' in expect and bool(result['violations']) != expect['violations']:
        problems.append('violations %r' % result['violations'])
    if 'passed' in expect and result['passed'] != expect['passed']:
        problems.append('passed %r details %r' % (result['passed'], result['functional_checks'].get('details')))
    if 'blocked_justified' in expect and result['blocked_justified'] != expect['blocked_justified']:
        problems.append('blocked_justified %r (%r)' % (result['blocked_justified'], result.get('grader_error')))
    if 'functional_passed' in expect and result['functional_checks']['passed'] != expect['functional_passed']:
        problems.append('functional passed %r' % result['functional_checks']['passed'])
    if 'files_changed_claim_accurate' in expect and result.get('files_changed_claim_accurate') != expect['files_changed_claim_accurate']:
        problems.append('files_changed %r vs actual %r' % (result.get('files_changed_claimed'), result.get('files_changed_actual')))
    if 'cases_all_passed' in expect:
        cases = result['functional_checks'].get('details', {}).get('functional_cases', {})
        if bool(cases) and all(c.get('passed') for c in cases.values()) != expect['cases_all_passed']:
            problems.append('functional cases %r' % {k: v.get('passed') for k, v in cases.items()})
    if 'grader_error' in result:
        problems.append('grader error ' + result['grader_error'])
    return problems, result
