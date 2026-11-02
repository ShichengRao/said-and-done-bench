from pipeline import transform

def test_public_example():
    assert transform({'plan': {'phases': 1, 'capacity': {'a': [1]}, 'groups': [{'id': 'g', 'members': ['r'], 'load': [1], 'allowed': [['a']], 'handoffs': []}]}, 'proposals': []}) == {'ready': True, 'local_paths': {'g': [['a']]}, 'phase_witnesses': [{'g': 'a'}], 'assignment': {'g': ['a']}, 'obstruction': [], 'owner_request': {'proposal_ids': [], 'cost': 0, 'assignment': {'g': ['a']}}, 'blocker_codes': []}
