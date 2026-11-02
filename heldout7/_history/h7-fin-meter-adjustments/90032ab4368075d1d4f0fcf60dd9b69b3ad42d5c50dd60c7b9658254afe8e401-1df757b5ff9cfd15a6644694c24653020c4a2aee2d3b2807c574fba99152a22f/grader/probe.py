"""Trusted probe runner, executed by task_checks only in a temporary copy.

argv: <client code dir> <ops.json> <output.json> <scratch dir>. Imports the
candidate's meter_billing.service, executes each scenario's operations and
records raw outputs. All comparison happens in the trusted grader process.
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


results = {}
try:
    from meter_billing import service as api
except Exception as error:  # noqa: BLE001
    api = None; failure = type(error).__name__ + ': ' + str(error)[:200]
for name, ops in json.loads(Path(ops_file).read_text()).items():
    if api is None:
        results[name] = {'import_error': failure}; continue
    path = str(Path(scratch) / (name + '.db')); outputs = []
    for op in ops:
        kind = op['op']
        if kind == 'init':
            outputs.append(safe(lambda: api.initialize(path, copy.deepcopy(op['config']))))
        elif kind == 'close':
            outputs.append(safe(lambda: api.close(path, copy.deepcopy(op['command']))))
        elif kind == 'close_mutate':
            command = copy.deepcopy(op['command']); holder = {}
            def run():
                response = api.close(path, command); holder['copy'] = copy.deepcopy(response)
                command['readings'][0]['counter'] = 999
                if response.get('targets'):
                    response['targets'][0]['units'] = 999
                return holder['copy']
            outputs.append(safe(run))
        elif kind == 'snapshot':
            outputs.append(safe(lambda: api.snapshot(path)))
        elif kind == 'subprocess_snapshot':
            script = 'import sys,json; sys.path.insert(0,%r); from meter_billing import service; print(json.dumps(service.snapshot(%r)))' % (code, path)
            try:
                run = subprocess.run([sys.executable, '-I', '-c', script], capture_output=True, text=True, timeout=60)
                outputs.append(json.loads(run.stdout) if run.returncode == 0 else {'error': 'subprocess failed'})
            except Exception as error:  # noqa: BLE001
                outputs.append({'error': 'subprocess ' + type(error).__name__})
        elif kind == 'concurrent':
            barrier = threading.Barrier(op['calls'])
            def call(i):
                barrier.wait(timeout=30)
                return safe(lambda: api.close(path, copy.deepcopy(op['commands'][i % len(op['commands'])])))
            with ThreadPoolExecutor(max_workers=op['calls']) as pool:
                outputs.append(list(pool.map(call, range(op['calls']))))
    results[name] = outputs
Path(out_file).write_text(json.dumps(results))
