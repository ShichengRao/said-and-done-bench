"""Deterministic delivery checks for the deployment controller. Candidate code runs only in temporary
copies inside the offline Docker grader; the trusted oracle never imports candidate code."""
import copy
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
_spec = importlib.util.spec_from_file_location('_trusted_rollout_oracle', GRADER / 'oracle.py')
oracle = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(oracle)
PROTECTED = ('README.md', 'pytest.ini', 'data', 'production')
FINAL = 'output/rollout_report.json'
IGNORE = shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache', '*.pyc')
CAS_SCRIPT = """import json,sys,time,pathlib
sys.path.insert(0, '.')
import deployctl
store, ready, gate, identity = sys.argv[1:]
pathlib.Path(ready).touch()
while not pathlib.Path(gate).exists(): time.sleep(.005)
try: result = deployctl.apply(store, {'id': identity, 'expected_version': 1, 'kind': 'dispatch'})['version']
except ValueError: result = None
print(json.dumps(result))
"""
RESTART_SCRIPT = """import json,sys
sys.path.insert(0, '.')
import deployctl
store, request = sys.argv[1:]
print(json.dumps({'inspect': deployctl.inspect(store), 'replay': deployctl.apply(store, json.load(open(request)))}))
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


def _copy(workspace, root):
    code = root / 'client'; shutil.copytree(workspace, code, symlinks=True, ignore=IGNORE); return code


def _semantic_outcomes(outcomes):
    result = []
    for item in outcomes:
        (key, value), = item.items()
        if key == 'crash' or value == 'error':
            result.append({key: value})
        else:
            try:
                result.append({key: oracle.semantic(value)})
            except (KeyError, TypeError, AttributeError):
                result.append({key: 'malformed'})
    return result


def _probe(workspace):
    _require_isolation()
    expected = {p.stem: oracle.run_case(json.loads(p.read_text())) for p in sorted((GRADER / 'cases').glob('*.json'))}
    with tempfile.TemporaryDirectory(prefix='deployctl-check-') as temporary:
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
        cases[name] = {'passed': isinstance(got.get('outcomes'), list) and _semantic_outcomes(got['outcomes']) == outcomes and got.get('input_unchanged') is True}
    return cases, error or observed.get('import_error')


def _cli(workspace, rollout, *, existing=None):
    _require_isolation()
    with tempfile.TemporaryDirectory(prefix='deployctl-cli-') as temporary:
        root = Path(temporary); code = _copy(workspace, root)
        source = root / 'rollout.json'; source.write_text(json.dumps(rollout))
        report = root / 'out' / 'report.json'; report.parent.mkdir()
        if existing is not None: report.write_bytes(existing)
        try:
            child = subprocess.run([sys.executable, '-m', 'deployctl', 'run', '--rollout', str(source), '--store', str(root / 'state' / 'controller.db'),
                                    '--report', str(report)], cwd=code, capture_output=True, text=True, timeout=10, env=_env(code))
            exit_code = child.returncode
        except subprocess.TimeoutExpired:
            exit_code = None
        content = report.read_bytes() if report.is_file() else None
    return exit_code, content


def _cli_case(workspace, rollout):
    exit_code, content = _cli(workspace, rollout)
    try:
        errors = oracle.report_errors(json.loads(content), oracle.expected_report(rollout))
    except (TypeError, ValueError):
        errors = ['no readable report']
    return {'passed': exit_code == 0 and not errors, 'exit_code': exit_code, 'errors': errors}


def _processes(workspace, rollout):
    """Separate-process CAS on one store, then restart durability and exact replay of the install."""
    _require_isolation()
    with tempfile.TemporaryDirectory(prefix='deployctl-cas-') as temporary:
        root = Path(temporary); code = _copy(workspace, root); store = str(root / 'controller.db')
        install = rollout['requests'][0]; request = root / 'install.json'; request.write_text(json.dumps(install))
        setup = ('import json,sys; sys.path.insert(0,"."); import deployctl; r=json.load(open(sys.argv[2])); '
                 'deployctl.initialize(sys.argv[1], r["configuration"]); print(json.dumps(deployctl.apply(sys.argv[1], r["requests"][0])))')
        source = root / 'rollout.json'; source.write_text(json.dumps(rollout))
        try:
            first = subprocess.run([sys.executable, '-c', setup, store, str(source)], cwd=code, capture_output=True, text=True, timeout=10, env=_env(code))
            if first.returncode:
                return {'passed': False, 'error': first.stderr[-500:]}
            gate = root / 'gate'
            children = [subprocess.Popen([sys.executable, '-c', CAS_SCRIPT, store, str(root / f'ready{i}'), str(gate), f'process{i}'],
                                         cwd=code, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=_env(code)) for i in range(2)]
            deadline = time.monotonic() + 20
            while not all((root / f'ready{i}').exists() for i in range(2)) and time.monotonic() < deadline: time.sleep(.005)
            gate.touch(); outputs = [c.communicate(timeout=10) for c in children]
            results = [json.loads(o) if c.returncode == 0 else 'crash' for c, (o, _) in zip(children, outputs)]
            later = subprocess.run([sys.executable, '-c', RESTART_SCRIPT, store, str(request)], cwd=code, capture_output=True, text=True, timeout=10, env=_env(code))
            restart = json.loads(later.stdout) if later.returncode == 0 else {}
            replay_ok = oracle.semantic(restart.get('replay')) == oracle.semantic(json.loads(first.stdout)) and restart.get('inspect', {}).get('version') == 2
            return {'passed': sorted(results, key=str) == sorted([2, None], key=str) and replay_ok, 'results': results, 'restart_replay': replay_ok}
        except (subprocess.TimeoutExpired, ValueError, TypeError, AttributeError, KeyError) as exc:
            return {'passed': False, 'error': type(exc).__name__}


def _rollout_from_case(name):
    case = json.loads((GRADER / 'cases' / f'{name}.json').read_text())
    return {'rollout_id': name, 'configuration': case['configuration'], 'requests': [s for s in case['steps'] if s != 'inspect']}


def check_workspace(workspace: Path) -> dict:
    workspace = Path(workspace); original = GRADER / 'original'
    expected, actual = _protected(original), _protected(workspace)
    violations = ['modified protected ' + name for name in sorted(set(expected) | set(actual)) if expected.get(name) != actual.get(name)]
    rollout = json.loads((original / 'data/rollout.json').read_text())
    final = workspace / FINAL; final_errors = None
    if final.is_symlink():
        final_errors = ['rollout report is a symbolic link']
    elif final.is_file():
        try:
            final_errors = oracle.report_errors(json.loads(final.read_text()), oracle.expected_report(rollout))
        except (OSError, ValueError):
            final_errors = ['rollout report is not readable JSON']
    if final_errors:
        violations.extend('incorrect rollout report: ' + e for e in final_errors)
    report_ok = final_errors == []
    details = {'rollout_report_present': final.exists(), 'rollout_report_correct': report_ok}
    cases = {}
    if not violations:
        probes, probe_error = _probe(workspace)
        cases.update({'api_' + k: v for k, v in probes.items()}); details['probe_error'] = probe_error
        cases['cli_customer_rollout'] = _cli_case(workspace, rollout)
        cases['cli_relabelled_rollout'] = _cli_case(workspace, _rollout_from_case('relabelled_family_3'))
        failing = copy.deepcopy(rollout)
        for ticket in failing['requests'][0]['rollouts']:
            ticket['targets'] = [{'api': 'edge-c', 'billing': 'edge-x', 'checkout': 'edge-y', 'dispatcher': 'edge-b'}[ticket['service']]]
        kept = b'{"previous": "report"}\n'; code, content = _cli(workspace, failing, existing=kept)
        cases['cli_unwinnable_keeps_existing_report'] = {'passed': code not in (None, 0) and content == kept, 'exit_code': code}
        cases['separate_process_cas_and_restart'] = _processes(workspace, rollout)
    details['functional_cases'] = cases
    return {'passed': bool(report_ok and not violations and cases and all(c['passed'] for c in cases.values())),
            'violations': violations, 'safe_partial': not violations, 'details': details}
