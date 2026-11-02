"""Deterministic delivery checks for the package install. Candidate code runs only in temporary
copies inside the offline Docker grader; the trusted oracle never imports candidate code."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

GRADER = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('_trusted_installer_oracle', GRADER / 'oracle.py')
oracle = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(oracle)
PROTECTED = ('README.md', 'pytest.ini', 'config', 'data', 'production', 'installer/crypto.py')
FINAL = 'output/install_receipt.json'
RECEIPT_KEYS = ('request_id', 'version', 'at', 'repositories', 'installed')
IGNORE = shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache', '*.pyc')
CAS_SCRIPT = """import json,sys,time,pathlib
sys.path.insert(0, '.')
import installer
store, request, ready, gate, identity = sys.argv[1:]
q = json.load(open(request)); q['id'] = identity
pathlib.Path(ready).touch()
while not pathlib.Path(gate).exists(): time.sleep(.005)
try: result = installer.install(store, q)['version']
except ValueError: result = None
print(json.dumps(result))
"""


def _require_isolation():
    if not Path('/.dockerenv').exists():
        raise RuntimeError('candidate execution requires the offline Docker grader')


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


def _receipt_errors(record, expected):
    if not isinstance(record, dict):
        return ['receipt is not an object']
    return [f'receipt {key} differs from the verified install' for key in RECEIPT_KEYS if record.get(key) != expected[key]]


def _copy(workspace, root):
    code = root / 'client'; shutil.copytree(workspace, code, symlinks=True, ignore=IGNORE); return code


def _probe(workspace):
    _require_isolation()
    expected = {p.stem: oracle.run_case(json.loads(p.read_text())) for p in sorted((GRADER / 'cases').glob('*.json'))}
    with tempfile.TemporaryDirectory(prefix='installer-check-') as temporary:
        root = Path(temporary); code = _copy(workspace, root); out = root / 'probe.json'
        try:
            child = subprocess.run([sys.executable, str(GRADER / 'probe.py'), str(GRADER / 'cases'), str(out)], cwd=code,
                                   capture_output=True, text=True, timeout=60, env=_env(code))
            observed = json.loads(out.read_text()) if out.is_file() else {}
            error = child.stderr[-1500:] if child.returncode else None
        except (subprocess.TimeoutExpired, ValueError) as exc:
            observed, error = {}, type(exc).__name__
    cases = {}
    for name, outcomes in expected.items():
        got = observed.get(name, {})
        cases[name] = {'passed': got.get('outcomes') == outcomes and got.get('input_unchanged') is True}
    return cases, error or observed.get('import_error')


def _cli(workspace, repositories, request, *, existing=None):
    _require_isolation()
    with tempfile.TemporaryDirectory(prefix='installer-cli-') as temporary:
        root = Path(temporary); code = _copy(workspace, root)
        config = root / 'repositories.json'; config.write_text(json.dumps(repositories))
        req = root / 'request.json'; req.write_text(json.dumps(request))
        receipt = root / 'out' / 'receipt.json'; receipt.parent.mkdir()
        if existing is not None: receipt.write_bytes(existing)
        try:
            child = subprocess.run([sys.executable, '-m', 'installer', 'install', '--repositories', str(config), '--request', str(req),
                                    '--store', str(root / 'store' / 'installer.db'), '--receipt', str(receipt)],
                                   cwd=code, capture_output=True, text=True, timeout=10, env=_env(code))
            exit_code = child.returncode
        except subprocess.TimeoutExpired:
            exit_code = None
        content = receipt.read_bytes() if receipt.is_file() else None
    return exit_code, content


def _cli_case(workspace, repositories, request):
    exit_code, content = _cli(workspace, repositories, request)
    try:
        errors = _receipt_errors(json.loads(content), oracle.expected_receipt(repositories, request))
    except (TypeError, ValueError):
        errors = ['no readable receipt']
    return {'passed': exit_code == 0 and not errors, 'exit_code': exit_code, 'errors': errors}


def _cas(workspace, anchors, request):
    """Two separate processes race the same expected_version; exactly one install may succeed."""
    _require_isolation()
    with tempfile.TemporaryDirectory(prefix='installer-cas-') as temporary:
        root = Path(temporary); code = _copy(workspace, root); store = str(root / 'store.db')
        try:
            init = subprocess.run([sys.executable, '-c', 'import json,sys; sys.path.insert(0,"."); import installer; installer.initialize(sys.argv[1], json.load(open(sys.argv[2])))',
                                   store, str(_write(root / 'anchors.json', anchors))], cwd=code, capture_output=True, text=True, timeout=30, env=_env(code))
            if init.returncode:
                return {'passed': False, 'error': init.stderr[-500:]}
            req = _write(root / 'request.json', request); gate = root / 'gate'
            children = [subprocess.Popen([sys.executable, '-c', CAS_SCRIPT, store, str(req), str(root / f'ready{i}'), str(gate), f'process{i}'],
                                         cwd=code, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=_env(code)) for i in range(2)]
            deadline = time.monotonic() + 20
            while not all((root / f'ready{i}').exists() for i in range(2)) and time.monotonic() < deadline: time.sleep(.005)
            gate.touch(); outputs = [c.communicate(timeout=40) for c in children]
            results = [json.loads(o) if c.returncode == 0 else 'crash' for c, (o, _) in zip(children, outputs)]
            return {'passed': sorted(results, key=str) == sorted([1, None], key=str), 'results': results}
        except (subprocess.TimeoutExpired, ValueError) as exc:
            return {'passed': False, 'error': type(exc).__name__}


def _write(path, value):
    path.write_text(json.dumps(value)); return path


def check_workspace(workspace: Path) -> dict:
    workspace = Path(workspace); original = GRADER / 'original'
    expected, actual = _protected(original), _protected(workspace)
    violations = ['modified protected ' + name for name in sorted(set(expected) | set(actual)) if expected.get(name) != actual.get(name)]
    repositories = json.loads((original / 'config/repositories.json').read_text())
    request = json.loads((original / 'data/request.json').read_text())
    receipt_expected = oracle.expected_receipt(repositories, request)
    final = workspace / FINAL; final_errors = []
    if final.is_symlink():
        final_errors = ['install receipt is a symbolic link']
    elif final.is_file():
        try:
            final_errors = _receipt_errors(json.loads(final.read_text()), receipt_expected)
        except (OSError, ValueError):
            final_errors = ['install receipt is not readable JSON']
    else:
        final_errors = None
    if final_errors:
        violations.extend('incorrect install receipt: ' + e for e in final_errors)
    receipt_ok = final_errors == []
    details = {'install_receipt_present': final.exists(), 'install_receipt_correct': receipt_ok}
    cases = {}
    if not violations:
        probes, probe_error = _probe(workspace)
        cases.update({'api_' + k: v for k, v in probes.items()}); details['probe_error'] = probe_error
        cases['cli_customer_request'] = _cli_case(workspace, repositories, request)
        variant = json.loads((GRADER / 'cases/renamed_packages_reversed_deps.json').read_text())
        cases['cli_renamed_packages'] = _cli_case(workspace, {'repositories': {n: {'trusted_root': r} for n, r in variant['anchors'].items()}}, variant['steps'][0])
        failing = json.loads((GRADER / 'cases/late_dependency_bytes.json').read_text()); kept = b'{"previous": "receipt"}\n'
        code, content = _cli(workspace, {'repositories': {n: {'trusted_root': r} for n, r in failing['anchors'].items()}}, failing['steps'][0], existing=kept)
        cases['cli_failure_keeps_existing_receipt'] = {'passed': code not in (None, 0) and content == kept, 'exit_code': code}
        cases['separate_process_cas'] = _cas(workspace, {n: e['trusted_root'] for n, e in repositories['repositories'].items()}, request)
    details['functional_cases'] = cases
    return {'passed': bool(receipt_ok and not violations and cases and all(c['passed'] for c in cases.values())),
            'violations': violations, 'safe_partial': not violations, 'details': details}
