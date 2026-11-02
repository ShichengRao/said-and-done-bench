"""Author-side helpers for deliverable tests. Not part of any task folder.

Candidate-probe code in grader/task_checks.py refuses to run outside the offline
Docker grader. These tests SIMULATE that environment by replacing only the
_require_isolation guard inside the test process, and run everything in /tmp copies.
This is not a substitute for the coordinator's Docker integration run.
"""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DELIVERABLES = ROOT / 'deliverables'
sys.path.insert(0, str(ROOT / 'author_support'))


def task_dir(task_id):
    return DELIVERABLES / task_id


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_checks(task_id, simulate_isolation=True):
    grader = task_dir(task_id) / 'grader'
    sys.path.insert(0, str(grader))
    try:
        module = load_module(grader / 'task_checks.py', 'checks_' + task_id.replace('-', '_'))
    finally:
        sys.path.remove(str(grader))
    if simulate_isolation:
        module._require_isolation = lambda: None
    return module


def tree_digest(root, skip=('.git', '__pycache__', '.pytest_cache')):
    digest = {}
    for p in sorted(Path(root).rglob('*')):
        rel = p.relative_to(root)
        if any(part in skip for part in rel.parts) or p.suffix == '.pyc' or not p.is_file():
            continue
        digest[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return digest


def materialize(task_id, solution, destination):
    """Copy the pristine workspace, overlay a reference solution's files and run its run.sh."""
    destination = Path(destination)
    shutil.copytree(task_dir(task_id) / 'workspace', destination)
    result = None
    if solution:
        source = task_dir(task_id) / 'solutions' / solution
        if (source / 'files').is_dir():
            shutil.copytree(source / 'files', destination, dirs_exist_ok=True)
        if (source / 'run.sh').is_file():
            env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
            env.pop('PYTHONPATH', None)
            result = subprocess.run(['bash', str(source / 'run.sh')], cwd=destination, capture_output=True, text=True, timeout=600, env=env)
    for cache in list(destination.rglob('__pycache__')) + list(destination.rglob('.pytest_cache')):
        shutil.rmtree(cache, ignore_errors=True)
    return destination, result


def run_assess(task_id, workspace, tmp_path, *, outcome, decisions=None, files_changed=None):
    """Exercise the shared _review.assess with a synthetic record and optional bound review."""
    grader = task_dir(task_id) / 'grader'
    checks = load_checks(task_id)
    review_module = load_module(grader / '_review.py', 'review_' + task_id.replace('-', '_'))
    config = json.loads((grader / 'review_config.json').read_text())
    record = {'task': {'id': task_id, 'task_hash': config['task_hash']}, 'outcome': outcome,
              'submit': {'status': outcome, 'claims': {'files_changed': files_changed or []}}}
    tmp_path.mkdir(parents=True, exist_ok=True)
    record_path = tmp_path / 'record.json'; record_path.write_text(json.dumps(record))
    review_path = tmp_path / 'monitor' / 'offline_review' / 'semantic.json'
    if decisions is not None:
        binding = review_module.binding(record_path, workspace, grader, config)
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text(json.dumps({'schema_version': 1, 'provenance': 'post_run_author_adjudication', 'final': True,
                                           'binding': binding, 'reviewer': 'author-test', 'reviewed_at': '2026-11-02',
                                           'rationale': 'synthetic test review', 'evidence': ['reference response'],
                                           'decisions': decisions}))
    return review_module.assess(record_path=record_path, workspace=workspace, grader=grader,
                                review_path=review_path, task_check=checks.check_workspace)


def current_task_hash(task_id):
    from task_api import load_task, task_hash
    return task_hash(load_task(task_dir(task_id)))
