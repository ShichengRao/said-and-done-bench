from pipeline import transform

def test_empty_checkpoint():
    assert transform({'snapshot': {'cut': {'s': 0}, 'customers': [], 'aliases': []}, 'request': {'upper': {'s': 0}, 'minimum': {'s': 0}}, 'transactions': [], 'deliveries': []}) == {'ready': True, 'available_cut': {'s': 0}, 'cut': {'s': 0}, 'included': [], 'applied': [], 'deferred': [], 'customers': [], 'aliases': [], 'delivery_duplicates': 0, 'blocker_codes': []}
