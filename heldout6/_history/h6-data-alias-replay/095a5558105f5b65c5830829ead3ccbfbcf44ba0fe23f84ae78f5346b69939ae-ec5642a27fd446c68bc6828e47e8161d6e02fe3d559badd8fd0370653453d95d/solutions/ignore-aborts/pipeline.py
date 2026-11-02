import copy


def transform(bundle):
    snapshot, request = bundle['snapshot'], bundle['request']
    base, upper, floor = snapshot['cut'], request['upper'], request['minimum']
    shards = sorted(base)
    txns = {t['id']: t for t in bundle['transactions']}
    if len(txns) != len(bundle['transactions']):
        raise ValueError('duplicate transaction')
    logs = {}
    duplicates = 0
    for row in bundle['deliveries']:
        key = (row['shard'], row['offset'])
        if key in logs:
            if logs[key] != row:
                raise ValueError('conflicting delivery')
            duplicates += 1
        else:
            logs[key] = row
    for row in logs.values():
        if row['transaction'] not in txns:
            raise ValueError('unknown delivery transaction')
        t = txns[row['transaction']]
        if not any(p['shard'] == row['shard'] and p['first'] <= row['offset'] <= p['last'] for p in t['parts']):
            raise ValueError('delivery does not match transaction manifest')
    available = dict(base)
    for shard in shards:
        while available[shard] < upper[shard] and (shard, available[shard] + 1) in logs:
            available[shard] += 1
    def included(t, cut):
        return all(cut[p['shard']] >= p['last'] for p in t['parts'])
    cut = dict(available)
    while True:
        next_cut = dict(cut)
        for t in txns.values():
            present = any(cut[p['shard']] >= p['first'] for p in t['parts'])
            valid = (t['decision'] != 'unresolved' and included(t, cut)
                     and all(included(txns[d], cut) for d in t['depends']))
            if present and not valid:
                for p in t['parts']:
                    if cut[p['shard']] >= p['first']:
                        next_cut[p['shard']] = min(next_cut[p['shard']], p['first'] - 1)
        if cut == next_cut:
            break
        cut = next_cut
    retained = sorted((t for t in txns.values() if included(t, cut)), key=lambda t: t['order'])
    customers = {(c['tenant'], c['id']): copy.deepcopy(c) for c in snapshot['customers']}
    aliases = {(a['tenant'], a['alias']): a['customer'] for a in snapshot['aliases']}
    applied = []
    for t in retained:
        if False:
            continue
        for op in t['operations']:
            key = (op['tenant'], op['alias'])
            if op['kind'] == 'bind':
                if (op['tenant'], op['customer']) not in customers:
                    raise ValueError('unknown customer')
                aliases[key] = op['customer']
            elif op['kind'] == 'unbind':
                aliases.pop(key, None)
            else:
                if key not in aliases:
                    raise ValueError('unbound alias')
                customer = customers[(op['tenant'], aliases[key])]
                if op['kind'] == 'adjust':
                    if customer['seats'] + op['delta'] < 0:
                        raise ValueError('negative seats')
                    customer['seats'] += op['delta']
                elif op['kind'] == 'tier':
                    customer['tier'] = op['value']
                elif op['kind'] == 'close':
                    customer['active'] = False
        applied.append(t['id'])
    ready = all(cut[s] >= floor[s] for s in shards)
    return {'ready': ready, 'available_cut': available, 'cut': cut,
            'included': [t['id'] for t in retained], 'applied': applied,
            'deferred': sorted(t for t in txns if not included(txns[t], cut)),
            'customers': [customers[k] for k in sorted(customers)],
            'aliases': [{'tenant': a, 'alias': b, 'customer': aliases[a, b]} for a, b in sorted(aliases)],
            'delivery_duplicates': duplicates,
            'blocker_codes': [] if ready else ['checkpoint_below_requested_floor']}

import argparse,json,os,tempfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',default='data');p.add_argument('--output',default='output/report.json');a=p.parse_args()
    bundle={f.stem:json.loads(f.read_text()) for f in sorted(Path(a.input).glob('*.json'))}
    report=transform(bundle)
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=target.parent)
    try:
        with os.fdopen(fd,'w') as stream:json.dump(report,stream,sort_keys=True,indent=2);stream.write('\n')
        os.replace(name,target)
    finally:
        if os.path.exists(name):os.unlink(name)
if __name__=='__main__':main()
