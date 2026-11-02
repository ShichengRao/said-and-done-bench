import sys
def mutate(data,rng,seed):
    for c in data['contacts']: c['id'] += str(seed)
    for e in data['authority_events']: e['contact'] += str(seed)
    if seed%3 == 0:
        data['authority_events'].append({'tenant':'cedar','ticket':'T-901','contact':'P-28'+str(seed),'at':45,'sequence':9,'approved':True})
    if seed%4 == 0:
        data['authority_events'].append({'tenant':'cedar','ticket':'T-902','contact':'P-28'+str(seed),'at':49,'sequence':10,'approved':True})
    rng.shuffle(data['contacts']);rng.shuffle(data['tickets']);rng.shuffle(data['authority_events'])

def extra_checks():
    result=transform(copy.deepcopy(source))
    assert result['unresolved']==[{'tenant':'cedar','ticket':'T-901','authoritative_contacts':[],'email_candidates':['P-17','P-28'],'reason':'missing-authority'}]
    data=copy.deepcopy(source);data['authority_events']=[]
    assert len(transform(data)['unresolved'])==3

import copy
import importlib.util
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from pipeline import transform
from _oracle import transform as oracle
source = json.loads(Path('data/input.json').read_text())
expected = oracle(copy.deepcopy(source))
assert json.loads(Path('output/report.json').read_text()) == expected, 'submitted artifact does not match authoritative input'
assert transform(copy.deepcopy(source)) == expected, 'canonical transform'
for seed in range(17):
    data = copy.deepcopy(source)
    rng = random.Random(seed)
    mutate(data, rng, seed)
    before = copy.deepcopy(data)
    actual = transform(data)
    assert actual == oracle(copy.deepcopy(before)), ('variant', seed, actual, oracle(copy.deepcopy(before)))
    assert data == before, 'transform mutated input'
extra_checks()
print('canonical artifact and 17 generated variants passed')
