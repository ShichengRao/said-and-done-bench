import json

import pytest

import h7_support as h

TASK = 'h7-data-checkpoint-publish'
ROOT = h.task_dir(TASK)
oracle = h.load(ROOT / 'grader/oracle.py', '_cp_oracle')
prove = h.load(ROOT / 'author_only/prove.py', '_cp_prove')
SOLUTIONS = sorted(p.name for p in (ROOT / 'solutions').iterdir() if p.is_dir())
EXPORT = oracle.read_data(ROOT / 'workspace/data')


def test_structure_and_shared_grader():
    assert h.check_structure(TASK, 'complete') == []


def test_review_config_pinned():
    assert h.check_pin(TASK)


def test_workspace_has_no_outcome_hints():
    assert h.leak_scan(TASK, extra=(r'\bready\b', r'blocker_codes', r'floor', r'may still be achievable')) == []


def test_fixtures_reused_byte_for_byte():
    previous = h.ROOT / 'previous/h6-data-alias-replay/workspace'
    for name in ('data/snapshot.json', 'data/request.json', 'data/transactions.json', 'data/deliveries.json', 'production/state.json'):
        assert h.sha(previous / name) == h.sha(ROOT / 'workspace' / name)


def test_independent_proof_agrees_with_oracle_and_generated_output():
    recorded = json.loads((ROOT / 'author_only/proof_result.json').read_text())
    want = oracle.expected(EXPORT)
    generated = json.loads((ROOT / 'author_only/expected_checkpoint.json').read_text())
    assert generated == want
    assert want['cut'] == recorded['greatest_cut'] and recorded['meets_minimum']
    assert want['included'] == recorded['included'] and want['applied'] == recorded['applied']
    seats = {'%s/%s' % (c['tenant'], c['id']): c['seats'] for c in want['customers']}
    assert seats == recorded['snapshot']['seats']
    assert prove.greatest()[0] == (2, 2, 2)


def test_nearby_cases_cover_both_outcomes():
    outcomes = [oracle.expected(b) is None for _, b in oracle.nearby_cases(EXPORT)]
    assert any(outcomes) and not all(outcomes)


def test_pristine_public_tests_pass(tmp_path):
    workspace, _ = h.apply_solution(TASK, 'unrelated-refusal', tmp_path)
    assert h.run_public_tests(workspace)[0] == 0


@pytest.mark.parametrize('name', SOLUTIONS)
def test_reference_outcome_author_simulation(name, tmp_path):
    workspace, _ = h.apply_solution(TASK, name, tmp_path)
    meta, result = h.grade_reference(TASK, name, workspace, tmp_path / 'run')
    assert 'grader_error' not in result, result
    assert h.expectation_problems(meta, result) == [], result
