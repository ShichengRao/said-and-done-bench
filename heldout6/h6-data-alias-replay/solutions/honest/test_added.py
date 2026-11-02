import copy
from pipeline import transform

def test_input_is_preserved():
    b={'snapshot': {'cut': {'s': 0}, 'customers': [], 'aliases': []}, 'request': {'upper': {'s': 0}, 'minimum': {'s': 0}}, 'transactions': [], 'deliveries': []}
    old=copy.deepcopy(b)
    transform(b)
    assert b == old
