from pipeline import transform

def test_public_example():
    assert transform({'evidence': {'owners': {'d': 'o'}, 'grants': [['o', 'team']], 'streams': [[{'id': 'cache', 'kind': 'copy', 'source': {'kind': 'document', 'id': 'd'}}, {'id': 'delivered', 'kind': 'receipt', 'copy': 'cache', 'audience': 'team'}]], 'before': []}, 'proposals': []}) == {'ready': True, 'classification': 'verified_safe', 'serialization_count': 1, 'safe_count': 1, 'unsafe_count': 0, 'first_safe_order': ['cache', 'delivered'], 'first_unsafe': None, 'owner_request': {'proposal_ids': [], 'cost': 0, 'serialization_count': 1, 'first_order': ['cache', 'delivered']}, 'blocker_codes': []}
