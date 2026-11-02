"""Trusted probe runner, executed by task_checks only in a temporary copy.

argv: <client code dir> <ops.json> <output.json> <scratch dir>. Imports the
candidate's refund_worker.service, executes each scenario's operations and
records raw outputs by tag. All checking happens in the trusted grader process.
"""
import copy
import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

code, ops_file, out_file, scratch = sys.argv[1:5]
sys.path.insert(0, code)


def safe(call):
    try:
        return json.loads(json.dumps(call()))
    except ValueError:
        return {'error': 'ValueError'}
    except Exception as error:  # noqa: BLE001 - diagnostics only
        return {'error': 'unexpected ' + type(error).__name__ + ': ' + str(error)[:200]}


CHILD = ('import json,sys; sys.path.insert(0,sys.argv[1]); from refund_worker import service as r; '
         'print(json.dumps({"snapshot":r.snapshot(sys.argv[2]),"replay":r.apply(sys.argv[2],json.loads(sys.argv[3]))}))')


def resolve(path, command):
    command = copy.deepcopy(command)
    if command.get('expected_version') == '@current':
        command['expected_version'] = next(x['version'] for x in api.snapshot(path)['refunds'] if x['id'] == command['refund'])
    return command


results = {}
try:
    from refund_worker import service as api
except Exception as error:  # noqa: BLE001
    api = None; failure = type(error).__name__ + ': ' + str(error)[:200]
for name, ops in json.loads(Path(ops_file).read_text()).items():
    if api is None:
        results[name] = {'import_error': failure}; continue
    path = str(Path(scratch) / (name + '.db')); outputs = {}
    for op in ops:
        kind = op['op']
        if kind == 'init':
            value = safe(lambda: api.initialize(path, copy.deepcopy(op['captures'])))
        elif kind == 'apply':
            value = safe(lambda: api.apply(path, resolve(path, op['command'])))
        elif kind == 'apply_mutate':
            def run():
                command = resolve(path, op['command']); response = api.apply(path, command); kept = copy.deepcopy(response)
                command['worker'] = 'mutated'
                if isinstance(response.get('provider_operation'), dict) and response['provider_operation'].get('lease'):
                    response['provider_operation']['lease']['token'] = 'mutated'
                return kept
            value = safe(run)
        elif kind == 'snapshot':
            value = safe(lambda: api.snapshot(path))
        elif kind == 'subprocess':
            try:
                child = subprocess.run([sys.executable, '-I', '-c', CHILD, code, path, json.dumps(op['command'])], capture_output=True, text=True, timeout=60)
                value = json.loads(child.stdout) if child.returncode == 0 else {'error': 'subprocess failed'}
            except Exception as error:  # noqa: BLE001
                value = {'error': 'subprocess ' + type(error).__name__}
        elif kind == 'concurrent':
            barrier = threading.Barrier(len(op['commands']))
            def call(i):
                barrier.wait(timeout=30)
                return safe(lambda: api.apply(path, copy.deepcopy(op['commands'][i])))
            with ThreadPoolExecutor(max_workers=len(op['commands'])) as pool:
                value = list(pool.map(call, range(len(op['commands']))))
        else:
            value = {'error': 'unknown op'}
        outputs[op['tag']] = value
    results[name] = outputs
Path(out_file).write_text(json.dumps(results))
