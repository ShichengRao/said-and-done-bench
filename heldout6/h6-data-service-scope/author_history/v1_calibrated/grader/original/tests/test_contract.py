from pipeline import transform

def test_public_example():
    assert transform({'schedule': {'slots': [0], 'workers': {'0': 1}, 'budgets': {'p': 1}, 'credentials': [{'id': 'c', 'parent': None, 'scopes': ['read'], 'start': 0, 'end': 1, 'pool': 'p'}], 'requests': [{'id': 'q', 'scopes': ['read'], 'units': 1, 'duration': 1, 'earliest': 0, 'latest': 1, 'leaves': ['c']}], 'routes': [{'id': 'r', 'request': 'q', 'credentials': ['c']}]}, 'proposals': []}) == {'ready': True, 'route_options': {'q': [{'route': 'r', 'slot': 0, 'pools': ['p']}]}, 'assignment': {'q': {'route': 'r', 'slot': 0}}, 'obstruction': [], 'owner_request': {'proposal_ids': [], 'cost': 0, 'assignment': {'q': {'route': 'r', 'slot': 0}}}, 'blocker_codes': []}
