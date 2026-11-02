from copy import deepcopy

def transform(bundle):
    snapshot=bundle['snapshot']; decisions=bundle['decisions']; deliveries=bundle['deliveries']; bindings=bundle['identity']
    customers={(c['tenant'],c['id']):deepcopy(c) for c in snapshot['customers']}
    if len(customers)!=len(snapshot['customers']): raise ValueError('duplicate customer')
    watermarks=dict(snapshot['watermarks']); as_of=snapshot['as_of']
    txs={}
    for row in decisions:
        key=(row['tenant'],row['tx'])
        if key in txs and txs[key]!=row: raise ValueError('conflicting transaction decision')
        txs[key]=row
    seqs=set()
    for row in txs.values():
        key=(row['tenant'],row['seq'])
        if key in seqs: raise ValueError('duplicate decision sequence')
        seqs.add(key)
    unique={}; duplicate=0
    for row in deliveries:
        key=(row['tenant'],row['stream'],row['offset'])
        if key in unique:
            if unique[key]!=row: raise ValueError('conflicting delivery')
            duplicate+=1
        else: unique[key]=row
    applied=[]
    for tx in sorted(txs.values(),key=lambda r:(r['seq'],r['tenant'],r['tx'])):
        tenant=tx['tenant'];seq=tx['seq']
        if seq>as_of or seq<=snapshot['watermarks'].get(tenant,0): continue
        watermarks[tenant]=max(watermarks.get(tenant,0),seq)
        if tx['decision']=='abort': pass
        rows=[row for row in unique.values() if row['tenant']==tenant and row['tx']==tx['tx']]
        members={(r['stream'],r['offset']) for r in rows}
        wanted={tuple(x) for x in tx['members']}
        if len(wanted)!=len(tx['members']) or members!=wanted: raise ValueError('transaction member mismatch')
        if sorted(r['order'] for r in rows)!=list(range(len(rows))): raise ValueError('transaction order gap')
        staged=deepcopy(customers);targets=[]
        for row in sorted(rows,key=lambda r:r['order']):
            candidates={b['customer'] for b in bindings if b['tenant']==tenant and b['alias']==row['alias'] and b['from']<=row['at'] and (b['until'] is None or row['at']<b['until'])}
            if len(candidates)!=1: raise ValueError('unresolved identity')
            target=candidates.pop();key=(tenant,target)
            if key not in staged: raise ValueError('unknown customer')
            customer=staged[key];op=row['op'];value=row['value']
            if op=='seats_delta':
                if type(value) is not int: raise ValueError('invalid seat delta')
                customer['seats']+=value
            elif op=='tier':
                if not isinstance(value,str): raise ValueError('invalid tier')
                customer['tier']=value
            elif op=='active':
                if type(value) is not bool: raise ValueError('invalid active')
                customer['active']=value
            else: raise ValueError('unknown operation')
            targets.append(target)
        if any(c['seats']<0 for c in staged.values()): raise ValueError('negative committed balance')
        customers=staged
        applied.append({'tenant':tenant,'tx':tx['tx'],'seq':seq,'targets':targets})
    return {'customers':[customers[k] for k in sorted(customers)],'watermarks':dict(sorted(watermarks.items())),'applied':applied,'delivery_duplicates':duplicate,'blocker_codes':[]}

import argparse
import json
import os
import tempfile
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input', default='data')
    parser.add_argument('--output', default='output/report.json')
    args=parser.parse_args()
    bundle={p.stem:json.loads(p.read_text()) for p in sorted(Path(args.input).glob('*.json'))}
    result=transform(bundle)
    destination=Path(args.output); destination.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=destination.parent)
    try:
        with os.fdopen(fd,'w') as stream: json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
        os.replace(name,destination)
    finally:
        if os.path.exists(name): os.unlink(name)
if __name__=='__main__': main()
