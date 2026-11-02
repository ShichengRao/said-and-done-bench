import json
import shutil
import subprocess
import sys
import pytest
import authoring_helpers as h

TASK_ID = 'h7-fin-payout-release'
TASK = h.task_dir(TASK_ID)


def test_package_structure_and_pin():
    assert h.package_problems(TASK_ID) == []


def test_author_proof_reproduces(tmp_path):
    saved = (TASK / 'author_only/proof_result.json').read_text()
    run = subprocess.run([sys.executable, str(TASK / 'author_only/prove.py')], capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == json.loads(saved)
    assert (TASK / 'author_only/proof_result.json').read_text() == saved


def test_public_tests_on_pristine_workspace(tmp_path):
    shutil.copytree(TASK / 'workspace', tmp_path / 'ws')
    run = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider'], cwd=tmp_path / 'ws', capture_output=True, text=True, timeout=120)
    # Resolver/replay tests pass; the bridge-scheduling test describes the unfinished feature.
    assert '1 failed, 5 passed' in run.stdout, run.stdout


def test_feasible_counterpart_through_reference_cli(tmp_path):
    oracle = h.load_module(TASK / 'grader/oracle.py', 'payout_counterpart_oracle')
    h.materialize(TASK_ID, 'honest-implemented', tmp_path / 'ws')
    base = oracle.read_batch(TASK / 'workspace/data')
    assert not oracle.releasable(base)
    batch = dict(oracle.variants(base))['signed_early_D_bridge']
    oracle.write_batch(tmp_path / 'counterpart', batch)
    out = tmp_path / 'release.json'
    run = subprocess.run([sys.executable, '-m', 'payout_release', 'schedule', '--data', str(tmp_path / 'counterpart'), '--output', str(out)],
                         cwd=tmp_path / 'ws', capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    assert oracle.validate_release(json.loads(out.read_text()), batch) == []


@pytest.mark.parametrize('solution', h.solutions(TASK_ID))
def test_reference_solution_grading(solution, tmp_path):
    problems, _ = h.check_solution(TASK_ID, solution, tmp_path)
    assert problems == []
