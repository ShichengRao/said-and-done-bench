"""Trusted probe runner, executed by task_checks only in a temporary copy.

argv: <client code dir> <ops.json> <output.json> <scratch dir>. Imports the
candidate's procurement.service, executes each scenario's operations and records
raw outputs. All comparison happens in the trusted grader process.
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


REPLAY = ('import json,sys; sys.path.insert(0,sys.argv[1]); from procurement import service as p; '
          'q=json.loads(sys.argv[3]); print(json.dumps({"replay":p.apply(sys.argv[2],q),"snapshot":p.snapshot(sys.argv[2])}))')
results = {}
try:
    from procurement import service as api
except Exception as error:  # noqa: BLE001
    api = None; failure = type(error).__name__ + ': ' + str(error)[:200]
for name, ops in json.loads(Path(ops_file).read_text()).items():
    if api is None:
        results[name] = {'import_error': failure}; continue
    path = str(Path(scratch) / (name + '.db')); outputs = []
    for op in ops:
        kind = op['op']
        if kind == 'init':
            outputs.append(safe(lambda: api.initialize(path, copy.deepcopy(op['catalog']))))
        elif kind == 'apply':
            outputs.append(safe(lambda: api.apply(path, copy.deepcopy(op['command']))))
        elif kind == 'apply_mutate':
            def run():
                command = copy.deepcopy(op['command']); response = api.apply(path, command); kept = copy.deepcopy(response)
                command['operation_id'] = 'mutated'
                for basket in response.get('baskets', []):
                    basket['units'].clear(); basket['version'] = -1
                return kept
            outputs.append(safe(run))
        elif kind == 'snapshot':
            outputs.append(safe(lambda: api.snapshot(path)))
        elif kind == 'subprocess_replay':
            try:
                run = subprocess.run([sys.executable, '-I', '-c', REPLAY, code, path, json.dumps(op['command'])], capture_output=True, text=True, timeout=60)
                outputs.append(json.loads(run.stdout) if run.returncode == 0 else {'error': 'subprocess failed'})
            except Exception as error:  # noqa: BLE001
                outputs.append({'error': 'subprocess ' + type(error).__name__})
        elif kind == 'concurrent':
            barrier = threading.Barrier(len(op['commands']))
            def call(i):
                barrier.wait(timeout=30)
                return safe(lambda: api.apply(path, copy.deepcopy(op['commands'][i])))
            with ThreadPoolExecutor(max_workers=len(op['commands'])) as pool:
                outputs.append(list(pool.map(call, range(len(op['commands'])))))
    results[name] = outputs
Path(out_file).write_text(json.dumps(results))
