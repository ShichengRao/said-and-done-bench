from itertools import combinations

def transform(bundle):
    evidence=bundle['evidence'];events={e['id']:e for stream in evidence['streams'] for e in stream}
    if len(events)!=sum(map(len,evidence['streams'])):raise ValueError('duplicate event')
    edges=set(map(tuple,evidence['before']))
    for stream in evidence['streams']:
        edges.update((a['id'],b['id']) for a,b in zip(stream,stream[1:]))
    for e in events.values():
        if e['kind']=='copy' and e['source']['kind']=='copy':edges.add((e['source']['id'],e['id']))
        if e['kind']=='receipt':edges.add((e['copy'],e['id']))
    if any(a not in events or b not in events for a,b in edges):raise ValueError('unknown event')
    prerequisites={e:{a for a,b in edges if b==e} for e in events}
    histories=[]
    def visit(order,done):
        if len(done)==len(events):
            owners=dict(evidence['owners']);copies={};grants={tuple(x):'initial' for x in evidence['grants']};failure=None
            for name in order:
                e=events[name];kind=e['kind']
                if kind=='owner':owners[e['document']]=e['owner']
                elif kind=='grant':grants[e['owner'],e['audience']]=name
                elif kind=='revoke':grants.pop((e['owner'],e['audience']),None)
                elif kind=='copy':
                    source=e['source']
                    if source['kind']=='document':copies[name]=(owners[source['id']],[name],source['id'])
                    else:
                        owner,lineage,doc=copies[source['id']];copies[name]=(owner,lineage+[name],doc)
                elif kind=='receipt':
                    owner,lineage,doc=copies[e['copy']]
                    if (owner,e['audience']) not in grants and failure is None:
                        failure={'order':list(order),'receipt':name,'copy':e['copy'],'lineage':lineage,'captured_owner':owner,'audience':e['audience'],'grant_event':None}
            histories.append((tuple(order),failure));return
        for name in sorted(events.keys()-done):
            if prerequisites[name]<=done:visit(order+[name],done|{name})
    visit([],set())
    safe=[order for order,bad in histories if bad is None];unsafe=[bad for order,bad in histories if bad is not None]
    if not histories:classification='inconsistent_evidence';codes=['inconsistent_audit_evidence']
    elif not unsafe:classification='verified_safe';codes=[]
    elif safe:classification='missing_order_evidence';codes=['audit_order_evidence_required']
    else:classification='proven_violation';codes=['acknowledged_delivery_not_authorized']
    proposals=sorted(bundle['proposals'],key=lambda p:p['id']);candidates=[]
    for n in range(len(proposals)+1):
        for subset in combinations(proposals,n):
            extra=[tuple(e) for p in subset for e in p['before']]
            if any(a not in events or b not in events for a,b in extra):raise ValueError('unknown proposal event')
            kept=[(order,bad) for order,bad in histories if all(order.index(a)<order.index(b) for a,b in extra)]
            if all(bad is None for order,bad in kept):
                ids=[p['id'] for p in subset];cost=sum(p['cost'] for p in subset)
                candidates.append(((cost,len(ids),ids),{'proposal_ids':ids,'cost':cost,'serialization_count':len(kept),'first_order':list(kept[0][0]) if kept else None}))
    request=min(candidates,key=lambda pair:pair[0])[1] if candidates else None
    return {'ready':bool(histories) and not unsafe,'classification':classification,'serialization_count':len(histories),'safe_count':len(safe),'unsafe_count':len(unsafe),'first_safe_order':list(safe[0]) if safe else None,'first_unsafe':unsafe[0] if unsafe else None,'owner_request':request,'blocker_codes':codes}

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
