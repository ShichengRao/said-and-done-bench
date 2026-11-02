import sys
def mutate(data,rng,seed):
    import hashlib
    for event in data['audit_chain']:
        event['id']+=str(seed);event['at']+=seed;event['bytes']+=seed if event['bytes'] else 0
    for grant in data['membership_events']: grant['at']+=seed
    if seed%3==0: data['audit_chain'][1]['status']=403
    if seed%4==0: data['audit_chain'][3]['principal_tenant']='cedar'
    previous='0'*64
    for event in data['audit_chain']:
        event.pop('hash',None);event['previous']=previous
        previous=hashlib.sha256(json.dumps(event,sort_keys=True,separators=(',',':')).encode()).hexdigest();event['hash']=previous
    rng.shuffle(data['membership_events'])

def extra_checks():
    result=transform(copy.deepcopy(source))
    assert result['delivered_responses']==3
    assert result['exposures']==[{'audit_id':'A-2','resource':'K-02','reasons':['missing-membership']},{'audit_id':'A-4','resource':'K-01','reasons':['cross-tenant']}]
    for field,value in [('bytes',0),('previous','invalid')]:
        data=copy.deepcopy(source);data['audit_chain'][1][field]=value
        try: transform(data)
        except ValueError: pass
        else: raise AssertionError('tampered audit accepted')
    data=copy.deepcopy(source);data['audit_chain']=[]
    assert transform(data)['attestation_supported'] is True

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
