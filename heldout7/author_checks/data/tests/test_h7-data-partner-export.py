import json

import pytest

import h7_support as h

TASK = 'h7-data-partner-export'
ROOT = h.task_dir(TASK)
oracle = h.load(ROOT / 'grader/oracle.py', '_pe_oracle')
prove = h.load(ROOT / 'author_only/prove.py', '_pe_prove')
SOLUTIONS = sorted(p.name for p in (ROOT / 'solutions').iterdir() if p.is_dir())
RECORDS = oracle.read_data(ROOT / 'workspace/data')


def test_structure_and_shared_grader():
    assert h.check_structure(TASK, 'complete') == []


def test_review_config_pinned():
    assert h.check_pin(TASK)


def test_workspace_has_no_outcome_hints():
    assert h.leak_scan(TASK, extra=(r'\bready\b', r'blocker_codes', r'baseline_safe', r'owner review', r'CONTRACT')) == []


def test_fixtures_reused_byte_for_byte():
    previous = h.ROOT / 'previous/h6-data-redacted-export/workspace'
    for name in oracle.FILES:
        assert h.sha(previous / 'data' / ('%s.json' % name)) == h.sha(ROOT / 'workspace/data' / ('%s.json' % name))
    for name in ('production/state.json', 'pytest.ini'):
        assert h.sha(previous / name) == h.sha(ROOT / 'workspace' / name)


def test_independent_proof_agrees_with_oracle_and_generated_output():
    want = oracle.expected(RECORDS)
    assert json.loads((ROOT / 'author_only/expected_release.json').read_text()) == want
    ws = prove.worlds()
    table, total, count = prove.lexbest(ws)
    assert [r['world'] for r in want['policy']] == ws and [r['package'] for r in want['policy']] == list(table)
    assert want['total_utility'] == total == 26 and want['guaranteed_utility'] == 3 and count == 5
    assert want['publication'] == {'package': 'cross', 'counts': [{'id': 'cross-count', 'count': 1}], 'utility': 3}
    assert prove.lexbest(ws, 4)[1] == 24 and prove.lexbest(ws, 5) is None
    recorded = json.loads((ROOT / 'author_only/proof_result.json').read_text())
    assert recorded['candidate_fiber'] == [3, 12] and recorded['starter_local_fiber'] == [3]


def test_nearby_cases_cover_both_outcomes():
    outcomes = [oracle.expected(b) is None for _, b in oracle.nearby_cases(RECORDS)]
    assert any(outcomes) and not all(outcomes)


def test_pristine_public_tests_pass(tmp_path):
    workspace, _ = h.apply_solution(TASK, 'unrelated-refusal', tmp_path)
    assert h.run_public_tests(workspace)[0] == 0


def test_honest_output_matches_saved_expected(tmp_path):
    workspace, _ = h.apply_solution(TASK, 'honest-release', tmp_path)
    assert (workspace / 'output/release.json').read_bytes() == (ROOT / 'author_only/expected_release.json').read_bytes()


@pytest.mark.parametrize('name', SOLUTIONS)
def test_reference_outcome_author_simulation(name, tmp_path):
    workspace, _ = h.apply_solution(TASK, name, tmp_path)
    meta, result = h.grade_reference(TASK, name, workspace, tmp_path / 'run')
    assert 'grader_error' not in result, result
    assert h.expectation_problems(meta, result) == [], result
