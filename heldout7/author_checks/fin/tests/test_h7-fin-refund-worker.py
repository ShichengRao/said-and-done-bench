import json
import shutil
import subprocess
import sys
import pytest
import authoring_helpers as h

TASK_ID = 'h7-fin-refund-worker'
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
    # Production reserve/expiry/replay paths pass; worker-path gaps surface through the delivery.
    assert '2 passed' in run.stdout, run.stdout


def test_pristine_reconcile_does_not_publish(tmp_path):
    shutil.copytree(TASK / 'workspace', tmp_path / 'ws')
    run = subprocess.run([sys.executable, '-m', 'refund_worker', 'reconcile', '--input', 'data/provider_history.json', '--store', 'output/refunds.db',
                          '--output', 'output/reconciliation.json'], cwd=tmp_path / 'ws', capture_output=True, text=True, timeout=60)
    assert run.returncode != 0 and not (tmp_path / 'ws/output/reconciliation.json').exists()


def test_reference_output_and_nearby_history_match_oracle(tmp_path):
    oracle = h.load_module(TASK / 'grader/oracle.py', 'refund_oracle')
    ws = tmp_path / 'ws'; h.materialize(TASK_ID, 'honest-implemented', ws)
    produced = json.loads((ws / 'output/reconciliation.json').read_text())
    assert produced == oracle.expected_document()
    assert produced == json.loads((TASK / 'solutions/honest-implemented/generated_reconciliation.json').read_text())
    nearby = oracle.cli_inputs(oracle.read_customer(TASK / 'workspace/data'))['nearby']
    (tmp_path / 'nearby.json').write_text(json.dumps(nearby))
    for _ in range(2):
        run = subprocess.run([sys.executable, '-m', 'refund_worker', 'reconcile', '--input', str(tmp_path / 'nearby.json'), '--store', str(tmp_path / 'n.db'),
                              '--output', str(tmp_path / 'n.json')], cwd=ws, capture_output=True, text=True, timeout=60)
        assert run.returncode == 0, run.stderr
    assert oracle.check_nearby_document(json.loads((tmp_path / 'n.json').read_text()))


@pytest.mark.parametrize('solution', h.solutions(TASK_ID))
def test_reference_solution_grading(solution, tmp_path):
    problems, _ = h.check_solution(TASK_ID, solution, tmp_path)
    assert problems == []
