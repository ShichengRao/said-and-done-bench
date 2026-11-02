"""Runs inside a temporary copy of the candidate workspace (cwd), in the offline grader only.
argv: cases_dir result_file. Exercises the public recovery API with a fresh store per case."""
import copy, json, sys, tempfile, traceback
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
cases_dir, result_file = Path(sys.argv[1]), Path(sys.argv[2])
results = {}
try:
    import recovery
except Exception:
    Path(result_file).write_text(json.dumps({'import_error': traceback.format_exc()[-1500:]})); raise SystemExit(0)
for path in sorted(cases_dir.glob('*.json')):
    case = json.loads(path.read_text()); outcomes = []; unchanged = True
    with tempfile.TemporaryDirectory(prefix='recovery-probe-') as tmp:
        store = str(Path(tmp) / 'recovery.db')
        try:
            for step in case['steps']:
                given = copy.deepcopy(step); op = step['op']
                try:
                    if op == 'initialize':
                        out = recovery.initialize(store, given['snapshot'])
                    elif op == 'inspect':
                        out = recovery.inspect(store)
                    elif op == 'ingest':
                        out = recovery.ingest(store, given['request_id'], given['expected_version'], given['batch'])
                    else:
                        out = recovery.advance(store, given['request_id'], given['expected_version'], given['target'])
                    outcomes.append({op: out})
                except ValueError:
                    outcomes.append({op: 'error'})
                unchanged = unchanged and given == step
        except Exception:
            outcomes.append({'crash': traceback.format_exc()[-800:]})
    results[path.stem] = {'outcomes': json.loads(json.dumps(outcomes, default=str)), 'input_unchanged': unchanged}
Path(result_file).write_text(json.dumps(results))
