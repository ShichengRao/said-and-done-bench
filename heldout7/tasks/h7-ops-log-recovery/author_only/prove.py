"""Author proof of the honest route: overlay solutions/honest on a temporary workspace copy, run its
run.sh (public + new tests, then the real restore command) and compare the checkpoint with the oracle."""
import importlib.util, json, os, shutil, subprocess, tempfile
from pathlib import Path
TASK = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('oracle', TASK / 'grader/oracle.py'); oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp) / 'ws'; shutil.copytree(TASK / 'workspace', ws); shutil.copytree(TASK / 'solutions/honest/files', ws, dirs_exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}; env['PYTHONDONTWRITEBYTECODE'] = '1'
    child = subprocess.run(['bash', str(TASK / 'solutions/honest/run.sh')], cwd=ws, capture_output=True, text=True, timeout=300, env=env)
    assert child.returncode == 0, child.stdout + child.stderr
    checkpoint = json.loads((ws / 'output/checkpoint.json').read_text())
history = json.loads((TASK / 'workspace/data/history.json').read_text())
assert oracle.checkpoint_errors(checkpoint, oracle.expected_checkpoint(history)) == []
result = {'honest_run': child.stdout.strip().splitlines()[-1], 'pytest': child.stdout.strip().splitlines()[-2], 'checkpoint_matches_oracle': True,
          'version': checkpoint['version'], 'frontier': checkpoint['frontier'], 'order': checkpoint['order'],
          'aborts': sorted(t for t, o in checkpoint['processed'].items() if o == 'abort')}
Path(__file__).with_name('proof_result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps(result))
