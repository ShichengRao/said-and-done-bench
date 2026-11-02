import json
import shutil
import subprocess
import sys
import pytest
import authoring_helpers as h

TASK_ID = 'h7-fin-order-reservations'
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
    # Production reserve/commit/replay paths pass; the exchange and planner gaps show up in the delivery.
    assert '2 passed' in run.stdout, run.stdout


def test_reference_output_matches_independent_oracle(tmp_path):
    oracle = h.load_module(TASK / 'grader/oracle.py', 'procurement_oracle')
    h.materialize(TASK_ID, 'honest-implemented', tmp_path / 'ws')
    produced = json.loads((tmp_path / 'ws/output/replacement_result.json').read_text())
    assert produced == oracle.expected_document(oracle.read_customer(TASK / 'workspace/data'))
    assert produced == json.loads((TASK / 'solutions/honest-implemented/generated_replacement_result.json').read_text())


@pytest.mark.parametrize('solution', h.solutions(TASK_ID))
def test_reference_solution_grading(solution, tmp_path):
    problems, _ = h.check_solution(TASK_ID, solution, tmp_path)
    assert problems == []
