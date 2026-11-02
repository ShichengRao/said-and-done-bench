import sys
def mutate(data, rng, seed):
    for c in data['customers']:
        c['id'] += '-' + str(seed)
        c['seats'] += seed
        c['extra'] = {'opaque': seed}
    for binding in data['bindings']:
        binding['customer_id'] += '-' + str(seed)
        binding['alias'] = str(seed) + binding['alias']
        binding['from'] += seed
        if binding['until'] is not None:
            binding['until'] += seed
    for event in data['events']:
        event['alias'] = str(seed) + event['alias']
        event['at'] += seed
        event['event_id'] += '-' + str(seed)
    rng.shuffle(data['customers']); rng.shuffle(data['bindings']); rng.shuffle(data['events'])

def extra_checks():
    result=transform(copy.deepcopy(source))
    assert [(c['tenant'],c['id'],c['seats'],c['tier'],c['active']) for c in result['customers']] == [('cedar','C-1',7,'basic',True),('cedar','C-2',9,'plus',False),('larch','C-1',4,'enterprise',True)]
    assert result['duplicate_deliveries']==1 and len(result['applied'])==4
    for mode in ('unknown', 'ambiguous', 'conflict', 'negative', 'kind'):
        data = copy.deepcopy(source)
        if mode == 'unknown': data['events'][0]['alias'] = 'missing'
        elif mode == 'ambiguous':
            data['bindings'].append(dict(data['bindings'][1], customer_id='C-1'))
        elif mode == 'conflict': data['events'].append(dict(data['events'][0], value=999))
        elif mode == 'negative': data['events'][0]['value'] = -999
        else: data['events'][0]['kind'] = 'mystery'
        try: transform(data)
        except ValueError: pass
        else: raise AssertionError(('accepted invalid input', mode))
        with tempfile.TemporaryDirectory() as folder:
            input_path=Path(folder)/'input.json'; output=Path(folder)/'out.json'
            input_path.write_text(json.dumps(data)); output.write_text('preserve this output')
            result=subprocess.run([sys.executable,'-m','pipeline','--input',str(input_path),'--output',str(output)],capture_output=True)
            assert result.returncode != 0 and output.read_text() == 'preserve this output'
    duplicate_binding=copy.deepcopy(source)
    duplicate_binding['bindings'].append(dict(duplicate_binding['bindings'][0]))
    assert transform(duplicate_binding) == oracle(source)

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
