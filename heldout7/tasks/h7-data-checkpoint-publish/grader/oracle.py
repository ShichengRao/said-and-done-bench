"""Trusted oracle for h7-data-checkpoint-publish.

`transform` and `small` are reused unchanged from the h6-data-alias-replay grader
(enumerates every finite cut vector; independent of the workspace fixed-point code).
"""
from itertools import product
from copy import deepcopy


def transform(b):
    s, r = b['snapshot'], b['request']
    ids = sorted(s['cut'])
    by_id = {t['id']: t for t in b['transactions']}
    if len(by_id) != len(b['transactions']):
        raise ValueError('duplicate transaction')
    seen = {}
    duplicates = 0
    for e in b['deliveries']:
        k = e['shard'], e['offset']
        if k in seen:
            if seen[k] != e:
                raise ValueError('conflicting delivery')
            duplicates += 1
        seen[k] = e
    for (shard, offset), delivery in seen.items():
        matching = [t['id'] for t in b['transactions'] for p in t['parts']
                    if p['shard'] == shard and p['first'] <= offset <= p['last']]
        if matching != [delivery['transaction']]:
            raise ValueError('invalid delivery manifest link')
    avail = {}
    for name in ids:
        absent = [i for i in range(s['cut'][name] + 1, r['upper'][name] + 1) if (name, i) not in seen]
        avail[name] = min(absent) - 1 if absent else r['upper'][name]
    valid = []
    for vector in product(*(range(s['cut'][k], avail[k] + 1) for k in ids)):
        c = dict(zip(ids, vector)); whole = set(); partial = False
        for t in b['transactions']:
            counts = [sum(c[p['shard']] >= i for i in range(p['first'], p['last'] + 1)) for p in t['parts']]
            size = sum(p['last'] - p['first'] + 1 for p in t['parts'])
            if 0 < sum(counts) < size:
                partial = True
            if sum(counts) == size:
                whole.add(t['id'])
        if partial or any(by_id[t]['decision'] == 'unresolved' or not set(by_id[t]['depends']) <= whole for t in whole):
            continue
        valid.append((vector, whole))
    greatest = tuple(max(v[i] for v, _ in valid) for i in range(len(ids)))
    whole = next(w for v, w in valid if v == greatest)
    cut = dict(zip(ids, greatest))
    state = deepcopy(s['customers']); binding = deepcopy(s['aliases']); applied = []
    ordered = sorted(whole, key=lambda t: by_id[t]['order'])
    for name in ordered:
        if by_id[name]['decision'] != 'commit':
            continue
        for op in by_id[name]['operations']:
            match = [a for a in binding if (a['tenant'], a['alias']) == (op['tenant'], op['alias'])]
            if op['kind'] == 'unbind':
                binding = [a for a in binding if a not in match]
            elif op['kind'] == 'bind':
                if not any(c['tenant'] == op['tenant'] and c['id'] == op['customer'] for c in state):
                    raise ValueError('missing customer')
                binding = [a for a in binding if a not in match]
                binding.append({'tenant': op['tenant'], 'alias': op['alias'], 'customer': op['customer']})
            else:
                if len(match) != 1:
                    raise ValueError('missing binding')
                c = next(c for c in state if c['tenant'] == op['tenant'] and c['id'] == match[0]['customer'])
                if op['kind'] == 'adjust':
                    c['seats'] = c['seats'] + op['delta']
                    if c['seats'] < 0:
                        raise ValueError('negative seats')
                if op['kind'] == 'tier':
                    c['tier'] = op['value']
                if op['kind'] == 'close':
                    c['active'] = False
        applied.append(name)
    ready = all(cut[k] >= r['minimum'][k] for k in ids)
    return {'ready': ready, 'available_cut': avail, 'cut': cut, 'included': ordered, 'applied': applied,
            'deferred': sorted(set(by_id) - whole), 'customers': sorted(state, key=lambda x: (x['tenant'], x['id'])),
            'aliases': sorted(binding, key=lambda x: (x['tenant'], x['alias'])), 'delivery_duplicates': duplicates,
            'blocker_codes': [] if ready else ['checkpoint_below_requested_floor']}


def small(seed):
    r=random.Random(seed);shards=['a','b','c'];base={s:seed%3 for s in shards};nexts=dict(base)
    b={'snapshot':{'cut':base,'customers':[{'tenant':'x','id':'one','seats':10,'tier':'base','active':True,'extra':{'keep':[1,2]}},{'tenant':'x','id':'two','seats':20,'tier':'plus','active':True}],'aliases':[{'tenant':'x','alias':'live','customer':'one'}]},'request':{},'transactions':[],'deliveries':[]}
    for n in range(5):
        chosen=r.sample(shards,r.randint(1,2));parts=[]
        for s in chosen:
            nexts[s]+=1;parts.append({'shard':s,'first':nexts[s],'last':nexts[s]})
        ops=[{'kind':'adjust','tenant':'x','alias':'live','delta':n+1}]
        if n==2:ops.insert(0,{'kind':'bind','tenant':'x','alias':'live','customer':'two'})
        t={'id':f't{n}','order':n,'decision':r.choice(['commit','commit','abort','unresolved']),'parts':parts,'depends':[f't{n-1}'] if n and r.random()<.65 else [],'operations':ops};b['transactions'].append(t)
        for p in parts:
            if r.random()<.85:b['deliveries'].append({'shard':p['shard'],'offset':p['first'],'transaction':t['id']})
    b['request']={'upper':nexts,'minimum':dict(base) if seed%2 else dict(nexts)}
    r.shuffle(b['transactions']);r.shuffle(b['deliveries'])
    return b


import json
import random
from pathlib import Path

FILES = ('snapshot', 'request', 'transactions', 'deliveries')
KEYS = ('cut', 'included', 'applied', 'deferred', 'customers', 'aliases')


def read_data(root):
    return {name: json.loads((Path(root) / ('%s.json' % name)).read_text()) for name in FILES}


def write_data(root, export):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        (root / ('%s.json' % name)).write_text(json.dumps(export[name], indent=2) + '\n')


def expected(export):
    """The checkpoint document the publisher must write, or None when it must refuse."""
    try:
        result = transform(deepcopy(export))
    except ValueError:
        return None
    if not result['ready']:
        return None
    return {key: result[key] for key in KEYS}


def compare(document, export):
    want = expected(export)
    if want is None:
        return ['no checkpoint should be published for this export']
    if not isinstance(document, dict):
        return ['checkpoint is not an object']
    return ['%s differs' % key for key in KEYS if document.get(key) != want[key]]


def nearby_cases(source):
    """(name, export) pairs: generated exports plus edits of the customer export."""
    for seed in (0, 1, 2, 3, 4, 5, 6, 7, 9, 11, 13, 19, 22, 25):
        yield 'generated-%d' % seed, small(seed)
    b = deepcopy(source); b['request']['minimum'] = dict(b['request']['upper']); yield 'minimum-at-upper', b
    b = deepcopy(source); b['transactions'].reverse(); b['deliveries'].reverse(); b['snapshot']['customers'].reverse(); b['snapshot']['aliases'].reverse(); yield 'permuted-export', b
    b = deepcopy(source); next(t for t in b['transactions'] if t['id'] == 'm77')['decision'] = 'commit'; yield 'm77-committed', b
    b = deepcopy(source); next(t for t in b['transactions'] if t['id'] == 'm77')['decision'] = 'abort'; yield 'm77-aborted', b
    b = deepcopy(source); b['deliveries'] = [d for d in b['deliveries'] if (d['shard'], d['offset']) != ('tickets', 1)]; yield 'gap-on-tickets', b
    b = deepcopy(source); b['deliveries'][0]['transaction'] = 'unknown'; yield 'unknown-transaction', b
    b = deepcopy(source); b['deliveries'].append({**b['deliveries'][0], 'transaction': 'm41'}); yield 'conflicting-delivery', b
    b = deepcopy(source); next(t for t in b['transactions'] if t['id'] == 'm41')['operations'][0]['delta'] = -100; yield 'negative-seats', b
    b = deepcopy(source); next(t for t in b['transactions'] if t['id'] == 'm41')['operations'][0]['alias'] = 'absent'; yield 'missing-binding', b
    b = small(1); b['transactions'] = [{'id': 'prepare', 'order': 1, 'decision': 'unresolved', 'parts': [{'shard': 'a', 'first': 2, 'last': 2}], 'depends': [], 'operations': []}, {'id': 'dependent', 'order': 2, 'decision': 'commit', 'parts': [{'shard': 'b', 'first': 2, 'last': 2}], 'depends': ['prepare'], 'operations': []}]; b['deliveries'] = [{'shard': 'a', 'offset': 2, 'transaction': 'prepare'}, {'shard': 'b', 'offset': 2, 'transaction': 'dependent'}]; b['request'] = {'upper': {'a': 2, 'b': 2, 'c': 1}, 'minimum': {'a': 1, 'b': 1, 'c': 1}}; yield 'cross-shard-dependency-only', b
    b = deepcopy(source); t = next(t for t in b['transactions'] if t['id'] == 'm96'); t['parts'][0]['last'] = 5; b['request']['upper'][t['parts'][0]['shard']] = 5; b['deliveries'].append({'shard': t['parts'][0]['shard'], 'offset': 5, 'transaction': 'm96'}); yield 'multi-offset-part', b
