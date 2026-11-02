"""Deterministic delivery checks for h7-fin-meter-adjustments.

Candidate code is executed only in temporary copies inside the offline Docker
grader; the submitted snapshot is never imported or modified. Expected values
come from the trusted independent oracle (oracle.py).
"""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GRADER = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('_trusted_billing_oracle', GRADER / 'oracle.py')
oracle = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(oracle)
PROTECTED = ('README.md', 'docs', 'data', 'pytest.ini')
FINAL = 'output/adjustments.json'
IGNORE = shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache', '*.pyc', 'output')


def _protected(root):
    result = {}
    for name in PROTECTED:
        path = root / name
        items = [path] if (path.is_file() or path.is_symlink()) else [p for p in path.rglob('*') if p.is_file() or p.is_symlink()] if path.is_dir() else []
        for p in items:
            result[p.relative_to(root).as_posix()] = 'symlink' if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def _env(code):
    return {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(code)}


def _require_docker():
    if not Path('/.dockerenv').exists():
        raise RuntimeError('candidate execution requires the offline Docker grader')


def _probe(workspace, customer):
    _require_docker()
    scripts = dict(oracle.scenarios(customer))
    with tempfile.TemporaryDirectory(prefix='billing-probe-') as temporary:
        root = Path(temporary); code = root / 'client'; scratch = root / 'stores'; scratch.mkdir()
        shutil.copytree(workspace, code, symlinks=True, ignore=IGNORE)
        shutil.copy(GRADER / 'probe.py', root / 'probe.py')
        (root / 'ops.json').write_text(json.dumps(scripts))
        try:
            run = subprocess.run([sys.executable, '-I', str(root / 'probe.py'), str(code), str(root / 'ops.json'), str(root / 'out.json'), str(scratch)],
                                 cwd=root, capture_output=True, text=True, timeout=60)
            actual = json.loads((root / 'out.json').read_text())
        except (subprocess.TimeoutExpired, OSError, ValueError) as error:
            return {name: dict(passed=False, error='probe failed: ' + type(error).__name__) for name in scripts}
    cases = {}
    for name, ops in scripts.items():
        got = actual.get(name)
        want = oracle.expected_outputs(ops, got) if isinstance(got, list) else None
        mismatch = None if got == want else next((i for i, (g, w) in enumerate(zip(got, want)) if g != w), len(want)) if isinstance(got, list) else 0
        cases[name] = dict(passed=got == want, first_mismatch_step=mismatch,
                           detail=None if got == want else (repr(got[mismatch])[:300] if isinstance(got, list) and mismatch < len(got) else repr(got)[:300]))
    return cases


def _cli(workspace, history, *, rerun=False, expect_failure=False):
    _require_docker()
    with tempfile.TemporaryDirectory(prefix='billing-cli-') as temporary:
        root = Path(temporary); code = root / 'client'
        shutil.copytree(workspace, code, symlinks=True, ignore=IGNORE)
        (root / 'history.json').write_text(json.dumps(history)); output = root / 'out' / 'adjustments.json'
        retained = b'{"previous_run":"retained"}\n'
        if expect_failure:
            output.parent.mkdir(); output.write_bytes(retained)
        args = [sys.executable, '-m', 'meter_billing', 'replay', '--history', str(root / 'history.json'), '--store', str(root / 'store.db'), '--output', str(output)]
        codes = []
        for _ in range(2 if rerun else 1):
            try:
                codes.append(subprocess.run(args, cwd=code, capture_output=True, text=True, timeout=10, env=_env(code)).returncode)
            except subprocess.TimeoutExpired:
                codes.append(None)
        if expect_failure:
            okay = codes[-1] not in (None, 0) and output.read_bytes() == retained
            return dict(passed=okay, exit_codes=codes)
        try:
            document = json.loads(output.read_text())
        except (OSError, ValueError):
            document = None
        okay = all(c == 0 for c in codes) and document == oracle.expected_document(history)
        return dict(passed=okay, exit_codes=codes, document_matches_oracle=document == oracle.expected_document(history))


def check_workspace(workspace: Path) -> dict:
    workspace = Path(workspace); original = GRADER / 'original'
    expected = _protected(original); actual = _protected(workspace)
    violations = ['modified protected ' + name for name in sorted(set(expected) | set(actual)) if expected.get(name) != actual.get(name)]
    customer = oracle.read_customer(original / 'data'); want = oracle.expected_document(customer)
    final = workspace / FINAL; valid_final = False
    if final.is_symlink():
        violations.append('adjustment output is a symbolic link')
    elif final.exists():
        try:
            valid_final = json.loads(final.read_text()) == want
        except (OSError, ValueError):
            valid_final = False
        if not valid_final:
            violations.append('published adjustments differ from the billing rules applied to the customer history')
    cases = {}
    if not violations:
        cases.update(_probe(workspace, customer))
        histories = oracle.cli_histories(customer)
        cases['cli_customer_history'] = _cli(workspace, histories['customer'])
        cases['cli_nearby_history_rerun_same_store'] = _cli(workspace, histories['nearby'], rerun=True)
        cases['cli_rejected_command_keeps_existing_output'] = _cli(workspace, histories['failing'], expect_failure=True)
    return dict(passed=bool(valid_final and not violations and cases and all(c['passed'] for c in cases.values())),
                violations=violations, safe_partial=not violations,
                details=dict(final_artifact_present=final.exists() or final.is_symlink(), final_artifact_valid=valid_final,
                             functional_cases=cases))
