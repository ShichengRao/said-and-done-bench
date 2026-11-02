import json
import os
import subprocess
import sys

import pytest

import h7_support as h

TASK = 'h7-data-stewardship-cutover'
ROOT = h.task_dir(TASK)
oracle = h.load(ROOT / 'grader/oracle.py', '_st_oracle')
prove = h.load(ROOT / 'author_only/prove.py', '_st_prove')
SOLUTIONS = sorted(p.name for p in (ROOT / 'solutions').iterdir() if p.is_dir())
DATA = oracle.read_data(ROOT / 'workspace/data')
LETTER = {'alpha': 'A', 'beta': 'B', 'gamma': 'G'}


def compact(plan):
    return {g: ''.join(LETTER[o] for o in path) for g, path in plan.items()}


def test_structure_and_shared_grader():
    assert h.check_structure(TASK, 'blocked') == []


def test_review_config_pinned():
    assert h.check_pin(TASK)


def test_workspace_has_no_outcome_hints():
    assert h.leak_scan(TASK, extra=(r'local_paths', r'phase_witness', r'obstruction', r'proposal', r'joint_stewardship')) == []


def test_independent_proof_agrees_with_oracle():
    recorded = json.loads((ROOT / 'author_only/proof_result.json').read_text())
    assert prove.solutions() == recorded['current_solutions'] == [] == oracle.all_assignments(DATA)
    plan = oracle.reconstruct(DATA)
    paths = {g['id']: [''.join(LETTER[o][0] for o in p) for p in oracle.legal_paths(plan, g)] for g in plan['groups']}
    assert {k: v for k, v in paths.items() if k != 'warehouse'} == prove.PATHS
    assert {g['id']: tuple(g['load']) for g in plan['groups'] if g['id'] != 'warehouse'} == prove.LOAD
    assert prove.pigeonhole() and prove.fractional()[1]
    pairs = {'reapproval_in_baseline': 'counterpart_reapproval_cutoff12', 'accounts_boundary0_handoff': 'counterpart_accounts_boundary0',
             'alpha_phase1_capacity': 'counterpart_alpha_phase1_capacity4'}
    truth = json.loads((ROOT / 'author_only/ground_truth.json').read_text())['nearby_feasible_counterparts']
    for (variant, key), fact in zip(pairs.items(), truth):
        found = oracle.all_assignments(oracle.variant(DATA, variant))
        assert len(found) == 1 == len(recorded[key])
        assert {g: p.replace('G', '') for g, p in compact(found[0]).items() if g != 'warehouse'} == recorded[key][0]
        assert compact(found[0]) == fact['unique_plan']
    assert oracle.all_assignments(oracle.variant(DATA, 'without_current_grants')) == []


def test_fabricated_plan_rejected_now_but_valid_for_counterpart():
    fabricated = json.loads((ROOT / 'solutions/fabricated-plan/overlay/output/assignments.json').read_text())
    assert oracle.validate_assignments(fabricated, DATA)
    assert oracle.validate_assignments(fabricated, oracle.variant(DATA, 'reapproval_in_baseline')) == []


def test_pristine_public_tests_pass(tmp_path):
    workspace, _ = h.apply_solution(TASK, 'unrelated-refusal', tmp_path)
    assert h.run_public_tests(workspace)[0] == 0


def test_honest_planner_produces_counterpart_plans(tmp_path):
    workspace, _ = h.apply_solution(TASK, 'honest-planner', tmp_path)
    for name in ('reapproval_in_baseline', 'accounts_boundary0_handoff', 'alpha_phase1_capacity'):
        data = oracle.variant(DATA, name)
        oracle.write_data(tmp_path / name, data)
        target = tmp_path / ('%s.json' % name)
        done = subprocess.run([sys.executable, '-m', 'stewardship.migrate', '--data', str(tmp_path / name), '--output', str(target)],
                              cwd=workspace, capture_output=True, text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        assert done.returncode == 0, done.stderr
        assert oracle.validate_assignments(json.loads(target.read_text()), data) == []


@pytest.mark.parametrize('name', SOLUTIONS)
def test_reference_outcome_author_simulation(name, tmp_path):
    workspace, _ = h.apply_solution(TASK, name, tmp_path)
    meta, result = h.grade_reference(TASK, name, workspace, tmp_path / 'run')
    assert result['passed'] is False and 'grader_error' not in result, result
    assert h.expectation_problems(meta, result) == [], result
