from pipeline import transform

def test_public_example():
    assert transform({'history': {'phases': 1, 'cutoff': 10, 'entries': [{'kind': 'record', 'entity': 'g', 'revision': 1, 'recorded': 1, 'effective': 0, 'approved': True, 'value': {'units': 1, 'owners': ['a']}}, {'kind': 'capacity', 'entity': 'a', 'revision': 1, 'recorded': 1, 'effective': 0, 'approved': True, 'value': {'units': 1}}]}, 'proposals': []}) == {'ready': True, 'local_paths': {'g': [['a']]}, 'phase_witnesses': [{'g': 'a'}], 'assignment': {'g': ['a']}, 'obstruction': [], 'owner_request': {'proposal_ids': [], 'cost': 0, 'assignment': {'g': ['a']}}, 'blocker_codes': [], 'resolved_plan': {'phases': 1, 'capacity': {'a': [1]}, 'groups': [{'id': 'g', 'members': ['g'], 'load': [1], 'allowed': [['a']], 'handoffs': []}]}}
