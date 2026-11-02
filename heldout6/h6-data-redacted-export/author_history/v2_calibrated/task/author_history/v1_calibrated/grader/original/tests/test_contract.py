from pipeline import transform

def test_public_example():
    assert transform({'roster': {'people': ['a', 'b'], 'aliases': [], 'consents': [{'person': 'a', 'revision': 1, 'allowed': True}, {'person': 'b', 'revision': 1, 'allowed': True}]}, 'prior': [], 'queries': [{'id': 'q', 'members': ['a', 'b'], 'utility': 1, 'approved': True}], 'policy': {'k': 2, 'minimum_utility': 1}}) == {'ready': True, 'baseline_safe': True, 'selected': ['q'], 'utility': 1, 'publication': [{'id': 'q', 'count': 2, 'utility': 1}], 'suppressed': [], 'atom_sizes': [2], 'blocker_codes': []}
