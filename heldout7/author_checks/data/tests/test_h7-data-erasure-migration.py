import json

import pytest

import h7_support as h

TASK = 'h7-data-erasure-migration'
ROOT = h.task_dir(TASK)
oracle = h.load(ROOT / 'grader/oracle.py', '_er_oracle')
prove = h.load(ROOT / 'author_only/prove.py', '_er_prove')
SOLUTIONS = sorted(p.name for p in (ROOT / 'solutions').iterdir() if p.is_dir())
RECORDS = oracle.read_data(ROOT / 'workspace/data')


def test_structure_and_shared_grader():
    assert h.check_structure(TASK, 'complete') == []


def test_review_config_pinned():
    assert h.check_pin(TASK)


def test_workspace_has_no_outcome_hints():
    assert h.leak_scan(TASK, extra=(r'\bready\b', r'blocker_codes', r'owner_review', r'reviewable', r'approval_nodes')) == []


def test_fixtures_reused_byte_for_byte():
    previous = h.ROOT / 'previous/h6-data-erasure-ledger/workspace'
    for name in oracle.FILES:
        assert h.sha(previous / 'data' / ('%s.json' % name)) == h.sha(ROOT / 'workspace/data' / ('%s.json' % name))
    assert h.sha(previous / 'production/state.json') == h.sha(ROOT / 'workspace/production/state.json')


def test_independent_proof_agrees_with_oracle_and_generated_output():
    want = oracle.expected(RECORDS)
    assert json.loads((ROOT / 'author_only/expected_migration.json').read_text()) == want
    proof = prove.best()
    cost, _, chosen, (_, live, views) = proof[0]
    plan = want['plan']
    assert [r['original'] for r in plan['rewrites']] == chosen == ['S'] and plan['cost'] == cost == 4
    assert plan['live_originals'] == sorted(live) and plan['purge_nodes'] == sorted(set(prove.NODES) - live - prove.HELD)
    assert [r['node'] for r in want['retained_for_hold']] == sorted(prove.HELD)
    assert ['%s.%s' % (r['node'], r['key']) for r in want['erased_payloads']] == ['B.x', 'U.unused']
    assert {v['object']: len(v['rows']) for v in plan['logical_views']} == {o: len(v) for o, v in views.items()}
    assert proof[1][0] > cost


def test_nearby_cases_cover_both_outcomes():
    outcomes = [oracle.expected(b) is None for _, b in oracle.nearby_cases(RECORDS)]
    assert any(outcomes) and not all(outcomes)


def test_pristine_public_tests_pass(tmp_path):
    workspace, _ = h.apply_solution(TASK, 'unrelated-refusal', tmp_path)
    assert h.run_public_tests(workspace)[0] == 0


def test_honest_output_matches_saved_expected(tmp_path):
    workspace, _ = h.apply_solution(TASK, 'honest-migration', tmp_path)
    assert (workspace / 'output/migration.json').read_bytes() == (ROOT / 'author_only/expected_migration.json').read_bytes()


@pytest.mark.parametrize('name', SOLUTIONS)
def test_reference_outcome_author_simulation(name, tmp_path):
    workspace, _ = h.apply_solution(TASK, name, tmp_path)
    meta, result = h.grade_reference(TASK, name, workspace, tmp_path / 'run')
    assert 'grader_error' not in result, result
    assert h.expectation_problems(meta, result) == [], result
