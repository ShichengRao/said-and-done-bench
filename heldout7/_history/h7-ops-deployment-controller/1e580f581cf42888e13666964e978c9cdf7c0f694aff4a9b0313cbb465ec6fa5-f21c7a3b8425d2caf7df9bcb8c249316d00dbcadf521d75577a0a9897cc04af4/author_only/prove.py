"""Author proof of the honest route: overlay solutions/honest on a temporary workspace copy, run its
run.sh (public + new tests, then the real rollout command) and compare the report with the oracle."""
import importlib.util, json, os, shutil, subprocess, tempfile
from pathlib import Path
TASK = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('oracle', TASK / 'grader/oracle.py'); oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp) / 'ws'; shutil.copytree(TASK / 'workspace', ws); shutil.copytree(TASK / 'solutions/honest/files', ws, dirs_exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}; env['PYTHONDONTWRITEBYTECODE'] = '1'
    child = subprocess.run(['bash', str(TASK / 'solutions/honest/run.sh')], cwd=ws, capture_output=True, text=True, timeout=300, env=env)
    assert child.returncode == 0, child.stdout + child.stderr
    report = json.loads((ws / 'output/rollout_report.json').read_text())
rollout = json.loads((TASK / 'workspace/data/rollout.json').read_text())
assert oracle.report_errors(report, oracle.expected_report(rollout)) == []
final = report['final']
result = {'honest_run': child.stdout.strip().splitlines()[-1], 'report_matches_oracle': True, 'final_version': final['version'],
          'rejected_requests': [r['id'] for r in report['results'] if not r['accepted']], 'quarantine': final['quarantine'],
          'placement': {v['service']: n for n, v in sorted(final['observed'].items()) if v}}
Path(__file__).with_name('proof_result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps(result))
