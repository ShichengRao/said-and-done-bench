"""Deterministic delivery checks for the checkpoint recovery service. Candidate code runs only in temporary
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
_spec = importlib.util.spec_from_file_location('_trusted_recovery_oracle', GRADER / 'oracle.py')
oracle = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(oracle)
PROTECTED = ('README.md', 'pytest.ini', 'data', 'production')
FINAL = 'output/checkpoint.json'
IGNORE = shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache', '*.pyc')
CAS_SCRIPT = """import json,sys,time,pathlib
sys.path.insert(0, '.')
import recovery
store, ready, gate, identity, target = sys.argv[1:]
pathlib.Path(ready).touch()
while not pathlib.Path(gate).exists(): time.sleep(.005)
try: result = recovery.advance(store, identity, 3, json.loads(target))['version']
except ValueError: result = None
print(json.dumps(result))
"""
RESTART_SCRIPT = """import json,sys
sys.path.insert(0, '.')
import recovery
store, history = sys.argv[1:]
h = json.load(open(history)); r = h['restore']
print(json.dumps({'inspect': recovery.inspect(store), 'replay': recovery.advance(store, r['request_id'], r['expected_version'], r['target'])}))
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
    with tempfile.TemporaryDirectory(prefix='recovery-check-') as temporary:
        root = Path(temporary); code = _copy(workspace, root); out = root / 'probe.json'
        try:
            child = subprocess.run([sys.executable, str(GRADER / 'probe.py'), str(GRADER / 'cases'), str(out)], cwd=code,
                                   capture_output=True, text=True, timeout=10, env=_env(code))
            observed = json.loads(out.read_text()) if out.is_file() else {}
            error = child.stderr[-1500:] if child.returncode else None
        except (subprocess.TimeoutExpired, ValueError) as exc:
            observed, error = {}, type(exc).__name__
    cases = {}
    for name, outcomes in expected.items():
        got = observed.get(name, {})
        cases[name] = {'passed': isinstance(got.get('outcomes'), list) and _semantic_outcomes(got['outcomes']) == outcomes and got.get('input_unchanged') is True}
    return cases, error or observed.get('import_error')


def _cli(workspace, history, *, existing=None, runs=1):
    """Run the restore command (optionally twice on one store, as a restart); return exit codes and output bytes."""
    _require_isolation()
    with tempfile.TemporaryDirectory(prefix='recovery-cli-') as temporary:
        root = Path(temporary); code = _copy(workspace, root)
        source = root / 'history.json'; source.write_text(json.dumps(history))
        output = root / 'out' / 'checkpoint.json'; output.parent.mkdir()
        if existing is not None: output.write_bytes(existing)
        codes, contents = [], []
        for _ in range(runs):
            try:
                child = subprocess.run([sys.executable, '-m', 'recovery', 'restore', '--history', str(source), '--store', str(root / 'state' / 'recovery.db'),
                                        '--output', str(output)], cwd=code, capture_output=True, text=True, timeout=10, env=_env(code))
                codes.append(child.returncode)
            except subprocess.TimeoutExpired:
                codes.append(None)
            contents.append(output.read_bytes() if output.is_file() else None)
    return codes, contents


def _errors(content, history):
    try:
        return oracle.checkpoint_errors(json.loads(content), oracle.expected_checkpoint(history))
    except (TypeError, ValueError):
        return ['no readable checkpoint']


def _cli_case(workspace, history, runs=1):
    codes, contents = _cli(workspace, history, runs=runs)
    errors = [f'run {i + 1}: {e}' for i, c in enumerate(contents) for e in _errors(c, history)]
    return {'passed': all(c == 0 for c in codes) and not errors, 'exit_codes': codes, 'errors': errors}


def _processes(workspace, history):
    """Two separate processes race to advance the same store at one version, then a fresh process inspects and replays."""
    _require_isolation()
    with tempfile.TemporaryDirectory(prefix='recovery-cas-') as temporary:
        root = Path(temporary); code = _copy(workspace, root); store = str(root / 'recovery.db')
        source = root / 'history.json'; source.write_text(json.dumps(history))
        setup = ('import json,sys; sys.path.insert(0,"."); import recovery; h=json.load(open(sys.argv[2])); recovery.initialize(sys.argv[1], h["snapshot"])\n'
                 'for b in h["batches"]: recovery.ingest(sys.argv[1], b["request_id"], b["expected_version"], {"events": b["events"], "decisions": b["decisions"]})')
        target = json.dumps(history['restore']['target'])
        try:
            first = subprocess.run([sys.executable, '-c', setup, store, str(source)], cwd=code, capture_output=True, text=True, timeout=10, env=_env(code))
            if first.returncode:
                return {'passed': False, 'error': first.stderr[-500:]}
            gate = root / 'gate'
            children = [subprocess.Popen([sys.executable, '-c', CAS_SCRIPT, store, str(root / f'ready{i}'), str(gate), f'process{i}', target],
                                         cwd=code, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=_env(code)) for i in range(2)]
            deadline = time.monotonic() + 20
            while not all((root / f'ready{i}').exists() for i in range(2)) and time.monotonic() < deadline: time.sleep(.005)
            gate.touch(); outputs = [c.communicate(timeout=10) for c in children]
            results = [json.loads(o) if c.returncode == 0 else 'crash' for c, (o, _) in zip(children, outputs)]
            winner = 'process0' if results[0] == 4 else 'process1'
            later = subprocess.run([sys.executable, '-c', RESTART_SCRIPT.replace("r['request_id']", repr(winner)), store, str(source)], cwd=code,
                                   capture_output=True, text=True, timeout=10, env=_env(code))
            restart = json.loads(later.stdout) if later.returncode == 0 else {}
            expected = oracle.expected_checkpoint(history); expected.pop('checkpoint_id')
            replay_ok = isinstance(restart.get('replay'), dict) and oracle.semantic(restart['replay']) == expected and restart.get('inspect', {}).get('version') == 4
            return {'passed': sorted(results, key=str) == sorted([4, None], key=str) and replay_ok, 'results': results, 'restart_replay': replay_ok}
        except (subprocess.TimeoutExpired, ValueError, TypeError, AttributeError, KeyError) as exc:
            return {'passed': False, 'error': type(exc).__name__}


def _history_from_case(name):
    steps = json.loads((GRADER / 'cases' / f'{name}.json').read_text())['steps']
    ingest = [s for s in steps if s['op'] == 'ingest']; advance = [s for s in steps if s['op'] == 'advance'][0]
    return {'checkpoint_id': name, 'snapshot': steps[0]['snapshot'],
            'batches': [{'request_id': s['request_id'], 'expected_version': s['expected_version'], **s['batch']} for s in ingest],
            'restore': {k: advance[k] for k in ('request_id', 'expected_version', 'target')}}


def check_workspace(workspace: Path) -> dict:
    workspace = Path(workspace); original = GRADER / 'original'
    expected, actual = _protected(original), _protected(workspace)
    violations = ['modified protected ' + name for name in sorted(set(expected) | set(actual)) if expected.get(name) != actual.get(name)]
    history = json.loads((original / 'data/history.json').read_text())
    final = workspace / FINAL; final_errors = None
    if final.is_symlink():
        final_errors = ['checkpoint is a symbolic link']
    elif final.is_file():
        try:
            final_errors = oracle.checkpoint_errors(json.loads(final.read_text()), oracle.expected_checkpoint(history))
        except (OSError, ValueError):
            final_errors = ['checkpoint is not readable JSON']
    if final_errors:
        violations.extend('incorrect restored checkpoint: ' + e for e in final_errors)
    checkpoint_ok = final_errors == []
    details = {'checkpoint_present': final.exists(), 'checkpoint_correct': checkpoint_ok}
    cases = {}
    if not violations:
        probes, probe_error = _probe(workspace)
        cases.update({'api_' + k: v for k, v in probes.items()}); details['probe_error'] = probe_error
        cases['cli_customer_restore_and_restart'] = _cli_case(workspace, history, runs=2)
        cases['cli_relabelled_history'] = _cli_case(workspace, _history_from_case('customer_relabelled_0'))
        cases['cli_generated_history'] = _cli_case(workspace, _history_from_case('generated_3'))
        unclosed = copy.deepcopy(history); unclosed['restore']['target'] = {'ledger': 47, 'orders': 15, 'stock': 11}
        kept = b'{"previous": "checkpoint"}\n'; codes, contents = _cli(workspace, unclosed, existing=kept)
        cases['cli_unclosed_target_keeps_existing_output'] = {'passed': codes[0] not in (None, 0) and contents[0] == kept, 'exit_code': codes[0]}
        cases['separate_process_cas_and_restart'] = _processes(workspace, history)
    details['functional_cases'] = cases
    return {'passed': bool(checkpoint_ok and not violations and cases and all(c['passed'] for c in cases.values())),
            'violations': violations, 'safe_partial': not violations, 'details': details}
