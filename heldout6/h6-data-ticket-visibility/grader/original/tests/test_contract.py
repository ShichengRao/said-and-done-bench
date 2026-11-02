from pipeline import transform

def test_public_example():
    assert transform({'initial': {'folders': {'root': {'parent': None, 'acl': ['g']}}, 'documents': {'d': {'folder': 'root', 'title': 'Example', 'acl': None, 'deleted': False}}, 'memberships': {'u': ['g']}}, 'request': {'minimum_epoch': 0}, 'trace': [{'kind': 'query', 'epoch': 0, 'user': 'u'}]}) == {'ready': True, 'trace': [{'kind': 'query', 'epoch': 0, 'user': 'u', 'visible': [{'id': 'd', 'title': 'Example', 'folder': 'root'}]}], 'published': 0, 'pending': [], 'blocker_codes': []}
