"""Independent bounded oracle: enumerate cut vectors, then interpret committed ops."""
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
