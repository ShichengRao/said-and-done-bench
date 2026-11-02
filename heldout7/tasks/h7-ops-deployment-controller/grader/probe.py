"""Runs inside a temporary copy of the candidate workspace (cwd), in the offline grader only.
argv: cases_dir result_file. Exercises the public deployctl API with a fresh store per case."""
import copy, json, sys, tempfile, traceback
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
cases_dir, result_file = Path(sys.argv[1]), Path(sys.argv[2])
results = {}
try:
    import deployctl
except Exception:
    Path(result_file).write_text(json.dumps({'import_error': traceback.format_exc()[-1500:]})); raise SystemExit(0)
for path in sorted(cases_dir.glob('*.json')):
    case = json.loads(path.read_text()); outcomes = []; unchanged = True
    with tempfile.TemporaryDirectory(prefix='deployctl-probe-') as tmp:
        store = str(Path(tmp) / 'controller.db')
        try:
            outcomes.append({'initialize': deployctl.initialize(store, copy.deepcopy(case['configuration']))})
            for step in case['steps']:
                if step == 'inspect':
                    outcomes.append({'inspect': deployctl.inspect(store)}); continue
                given = copy.deepcopy(step)
                try:
                    outcomes.append({'apply': deployctl.apply(store, given)})
                except ValueError:
                    outcomes.append({'apply': 'error'})
                unchanged = unchanged and given == step
        except Exception:
            outcomes.append({'crash': traceback.format_exc()[-800:]})
    results[path.stem] = {'outcomes': json.loads(json.dumps(outcomes, default=str)), 'input_unchanged': unchanged}
Path(result_file).write_text(json.dumps(results))
