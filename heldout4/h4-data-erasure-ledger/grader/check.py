import sys
def mutate(data,rng,seed):
    data['as_of'] += seed
    for r in data['requests']: r['effective'] += seed
    for h in data['holds']:
        h['starts'] += seed
        if h['ends'] is not None: h['ends'] += seed
    for r in data['records']:
        r['id'] += str(seed); r['opaque'] = [seed]
        for f in r['fields'].values(): f['collected'] += seed; f['value'] += str(seed)
    if seed % 2:
        data['holds'].append(dict(data['holds'][0],id='additional-hold',ends=None))
    if seed % 3 == 0: data['requests'].append(dict(data['requests'][0],effective=data['as_of']-3))
    rng.shuffle(data['records']); rng.shuffle(data['holds']); rng.shuffle(data['requests'])

def extra_checks():
    data=copy.deepcopy(source); data['requests']=[]
    assert transform(data) == oracle(data)
    data=copy.deepcopy(source); data['holds']=[]
    assert transform(data) == oracle(data)
    result=transform(copy.deepcopy(source))
    assert 'private@fiction.invalid' not in json.dumps(result['receipts'])
    assert result['receipts'][0]['erased_fields'] == ['email']
    assert result['receipts'][1]['removed_record'] is True

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
