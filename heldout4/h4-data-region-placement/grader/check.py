import sys
def mutate(data,rng,seed):
    for chunk in data['chunks']: chunk['bytes'] += seed * 3
    for d in data['destinations']: d['free_bytes'] += seed * 2
    if seed%3 == 0: data['destinations'][0]['free_bytes']=100000
    if seed%4 == 0: data['destinations'][1]['replica_regions']=['eu-west']
    rng.shuffle(data['chunks']);rng.shuffle(data['destinations']);rng.shuffle(data['datasets'])

def extra_checks():
    result=transform(copy.deepcopy(source))
    assert result['required_bytes']==1800 and result['selected'] is None
    assert result['destinations'][0]['rejections']==['capacity']
    data=copy.deepcopy(source);data['destinations'][0]['free_bytes']=1800
    assert transform(data)['selected']=='atlas-eu'

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
