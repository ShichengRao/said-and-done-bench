import sys
def mutate(data,rng,seed):
    data['at']+=seed
    for credential in data['credentials']:
        credential['expires']+=seed
        for grant in credential['grants']:
            grant['from']+=seed
            if grant['until'] is not None:grant['until']+=seed
    if seed%2==0: data['credentials'][0]['grants'].append({'resource':'tickets','operation':'erasure','effect':'allow','tenant':'cedar','region':'eu','from':data['at'],'until':None})
    if seed%3==0: data['credentials'][0]['grants'][0]['region']='us'
    if seed%4==0: data['credentials'][-1]['grants'][-1]['until']=data['at']
    rng.shuffle(data['credentials']);rng.shuffle(data['datasets'])

def extra_checks():
    result=transform(copy.deepcopy(source))
    assert result['selected'] is None
    byid={r['credential']:r for r in result['credentials']}
    assert byid['worker-current']['uncovered']==['tickets:erasure']
    assert byid['worker-regional']['uncovered']==['tickets:erasure']
    assert byid['personal-admin']['rejections']==['owner']
    assert byid['worker-archived']['rejections']==['expired']
    data=copy.deepcopy(source);data['credentials'][0]['grants'].append({'resource':'tickets','operation':'erasure','effect':'allow','tenant':'cedar','region':'eu','from':51,'until':None})
    assert transform(data)['selected'] is None

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
