from pipeline import transform

def test_public_example():
    assert transform({'placement': {'nodes': [{'id': 'a', 'region': 'eu', 'keys': ['k']}, {'id': 'b', 'region': 'eu', 'keys': ['k']}], 'templates': [{'id': 'ab', 'nodes': ['a', 'b']}], 'datasets': [{'id': 'g', 'units': 1, 'survivors': 1, 'regions': ['eu'], 'key': 'k', 'templates': ['ab']}], 'scenarios': [{'id': 's', 'down': ['a'], 'capacity': {'a': 0, 'b': 1}}]}, 'proposals': []}) == {'ready': True, 'eligible_templates': {'g': ['ab']}, 'robust_options': {'g': ['ab']}, 'scenario_witnesses': {'s': {'g': 'ab'}}, 'assignment': {'g': 'ab'}, 'obstruction': None, 'owner_request': {'proposal_ids': [], 'cost': 0, 'assignment': {'g': 'ab'}}, 'blocker_codes': []}
