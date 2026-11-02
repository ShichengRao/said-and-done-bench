from pipeline import transform

def test_public_example():
    assert transform({'schedule': {'as_of': 0, 'slots': [0], 'workers': {'0': 0}, 'budgets': {'root': 0}, 'credentials': [], 'requests': [], 'routes': []}, 'ledger': {'attempts': [], 'receipts': []}, 'proposals': []}) == {'ready': True, 'reservation_state': {}, 'availability': {'root': {'0': 0}}, 'route_options': {}, 'assignment': {}, 'obstruction': [], 'owner_request': {'proposal_ids': [], 'cost': 0, 'assignment': {}}, 'blocker_codes': []}
