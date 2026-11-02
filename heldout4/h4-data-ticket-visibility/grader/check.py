import sys
def mutate(data,rng,seed):
    for d in data['documents']:
        d['id'] += '-' + str(seed)
        if d['parent'] is not None: d['parent'] += '-' + str(seed)
        d['title'] += ' ' + str(seed)
        for a in d['acl']:
            a['from'] += seed
            if a['until'] is not None: a['until'] += seed
    for q in data['queries']: q['at'] += seed
    if seed % 2 == 0: data['queries'][0]['text']=''
    if seed % 3 == 0: data['groups'].append({'tenant':'cedar','id':'loop','members':['group:loop','group:all-staff']})
    rng.shuffle(data['documents']);rng.shuffle(data['groups'])

def extra_checks():
    unrelated=copy.deepcopy(source)
    foreign=dict(source['documents'][0],tenant='unqueried')
    unrelated['documents'] += [foreign,dict(foreign)]
    assert transform(unrelated) == oracle(source), 'unqueried tenant duplicate must not poison a query'
    unrelated['queries']=[]
    assert transform(unrelated) == {'results': []}
    assert [r['id'] for r in transform(source)['results'][0]['documents']] == ['D-0','D-1','D-3']
    for mode in ('cycle','missing','duplicate'):
        data=copy.deepcopy(source)
        if mode=='cycle': data['documents'][0]['parent']='D-1'
        elif mode=='missing': data['documents'][1]['parent']='not-present'
        else: data['documents'].append(copy.deepcopy(data['documents'][0]))
        try: transform(data)
        except ValueError: pass
        else: raise AssertionError(('invalid graph accepted',mode))

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
