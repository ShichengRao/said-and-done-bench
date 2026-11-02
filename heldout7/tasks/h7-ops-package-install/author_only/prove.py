"""Author proof of the honest route: overlay solutions/honest on a temporary workspace copy, run its
run.sh (public + new tests, then the real install command) and compare the receipt with the oracle."""
import importlib.util, json, os, shutil, subprocess, tempfile
from pathlib import Path
TASK = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('oracle', TASK / 'grader/oracle.py'); oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp) / 'ws'; shutil.copytree(TASK / 'workspace', ws); shutil.copytree(TASK / 'solutions/honest/files', ws, dirs_exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}; env['PYTHONDONTWRITEBYTECODE'] = '1'
    child = subprocess.run(['bash', str(TASK / 'solutions/honest/run.sh')], cwd=ws, capture_output=True, text=True, timeout=300, env=env)
    assert child.returncode == 0, child.stdout + child.stderr
    receipt = json.loads((ws / 'output/install_receipt.json').read_text())
repos = json.loads((TASK / 'workspace/config/repositories.json').read_text()); request = json.loads((TASK / 'workspace/data/request.json').read_text())
expected = oracle.expected_receipt(repos, request)
assert receipt == expected
result = {'honest_run': child.stdout.strip().splitlines()[-1], 'receipt_matches_oracle': True,
          'installed': [(e['repo'], e['path'], e['role']) for e in receipt['installed']],
          'repositories': {r: (v['root_version'], v['snapshot_version'], v['roles']) for r, v in receipt['repositories'].items()}}
Path(__file__).with_name('proof_result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps(result))
