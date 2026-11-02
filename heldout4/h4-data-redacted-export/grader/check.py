import sys
def mutate(data,rng,seed):
    for c in data['crm']: c['id'] += str(seed); c['email']='sensitive'+str(seed)
    for b in data['approved_bridge']: b['customer_id']+=str(seed); b['token']+=str(seed)
    for c in data['consent']: c['customer_id']+=str(seed)
    for t in data['tickets']: t['token']+=str(seed); t['id']+=str(seed)
    data['minimum_members'] = 2 + seed % 3
    data['tickets'].append(dict(data['tickets'][0],id='additional'+str(seed),revision=1))
    if seed%2: data['consent'].append(dict(data['consent'][0],at=99,sequence=99,allowed=False))
    rng.shuffle(data['crm']);rng.shuffle(data['approved_bridge']);rng.shuffle(data['consent']);rng.shuffle(data['tickets'])

def extra_checks():
    result=transform(copy.deepcopy(source))
    assert result['groups'] == [{'region':'EU','tier':'plus','member_count':3,'topics':{'billing':1,'setup':2}}]
    assert result['suppressed_groups']==1
    for mode in ('bridge','unknown','conflict','missing-crm'):
        data=copy.deepcopy(source)
        if mode=='bridge': data['approved_bridge'].append(dict(data['approved_bridge'][0]))
        elif mode=='unknown': data['tickets'][0]['token']='missing'; data['tickets'][-3]['token']='missing'
        elif mode=='missing-crm': data['crm'] = [c for c in data['crm'] if c['id'] != 'C-1']
        else: data['tickets'].append(dict(data['tickets'][0],topic='conflicting'))
        try: transform(data)
        except ValueError: pass
        else: raise AssertionError(('invalid identity/revision accepted',mode))

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
