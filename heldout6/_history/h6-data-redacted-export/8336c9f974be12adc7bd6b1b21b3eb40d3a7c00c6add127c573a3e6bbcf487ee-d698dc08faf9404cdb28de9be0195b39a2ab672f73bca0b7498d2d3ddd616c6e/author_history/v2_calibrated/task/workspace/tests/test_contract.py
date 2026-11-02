from pipeline import transform

def test_public_example():
    assert transform({'roster': {'people': ['a', 'b'], 'aliases': [], 'consents': [{'person': 'a', 'revision': 1, 'allowed': True}, {'person': 'b', 'revision': 1, 'allowed': True}]}, 'prior': [], 'queries': [{'id': 'total', 'members': ['a', 'b'], 'utility': 3, 'approved': True}], 'policy': {'max_changes': 2, 'protected': ['a', 'b'], 'minimum_utility': 3}, 'snapshots': {'old': {'a': 0, 'b': 1}, 'current': {'a': 0, 'b': 1}}}) == {'ready': True, 'baseline_safe': True, 'selected': ['total'], 'utility': 3, 'publication': [{'id': 'total', 'count': 1, 'utility': 3}], 'suppressed': [], 'baseline_candidate_count': 4, 'candidate_count': 2, 'protected_count': 2, 'ambiguous_protected_count': 2, 'blocker_codes': []}
