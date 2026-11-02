import json
import shutil
import subprocess
import sys
from pathlib import Path
import pytest
import authoring_helpers as h

TASK_ID = 'h7-fin-funding-scheduler'
TASK = h.task_dir(TASK_ID)


def test_package_structure_and_pin():
    assert h.package_problems(TASK_ID) == []


def test_author_proof_reproduces():
    run = subprocess.run([sys.executable, str(TASK / 'author_only/prove.py')], capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == json.loads((TASK / 'author_only/proof_result.json').read_text())


def test_public_tests_on_pristine_workspace(tmp_path):
    shutil.copytree(TASK / 'workspace', tmp_path / 'ws')
    run = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider'], cwd=tmp_path / 'ws', capture_output=True, text=True, timeout=120)
    # Adapter tests pass; the two scheduler tests describe the unbuilt feature.
    assert '2 failed, 5 passed' in run.stdout, run.stdout


def test_feasible_counterpart_through_reference_cli(tmp_path):
    oracle = h.load_module(TASK / 'grader/oracle.py', 'counterpart_oracle')
    h.materialize(TASK_ID, 'honest-implemented', tmp_path / 'ws')
    bundle = oracle.entitle(oracle.read_bundle(TASK / 'workspace/data'), 'O1-P', 'inspect-X')
    oracle.write_bundle(tmp_path / 'counterpart', bundle)
    out = tmp_path / 'schedule.json'
    run = subprocess.run([sys.executable, '-m', 'funding_scheduler', 'schedule', '--data', str(tmp_path / 'counterpart'), '--output', str(out)],
                         cwd=tmp_path / 'ws', capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    assert oracle.policy_count(bundle) == 6 and oracle.validate_schedule(json.loads(out.read_text()), bundle) == []


@pytest.mark.parametrize('solution', h.solutions(TASK_ID))
def test_reference_solution_grading(solution, tmp_path):
    problems, _ = h.check_solution(TASK_ID, solution, tmp_path)
    assert problems == []
