"""Independent oracle: weave sealed streams and evaluate each receipt by prefix queries."""
from itertools import combinations,product

def transform(b):
    ev=b['evidence'];streams=ev['streams'];events=[e for s in streams for e in s];by={e['id']:e for e in events}
    if len(by)!=len(events):raise ValueError('duplicate event')
    edges=list(map(tuple,ev['before']))
    edges += [(e['source']['id'],e['id']) for e in events if e['kind']=='copy' and e['source']['kind']=='copy']
    edges += [(e['copy'],e['id']) for e in events if e['kind']=='receipt']
    all_extra=[tuple(x) for p in b['proposals'] for x in p['before']]
    if any(x not in by or y not in by for x,y in edges+all_extra):raise ValueError('unknown event')
    def weaves(seqs):
        if not any(seqs):yield ();return
        for i,s in enumerate(seqs):
            if s:
                tails=list(seqs);tails[i]=s[1:]
                for rest in weaves(tails):yield (s[0]['id'],)+rest
    outcomes=[]
    for order in weaves(streams):
        pos={name:i for i,name in enumerate(order)}
        if not all(pos[a]<pos[c] for a,c in edges):continue
        bad=None
        for receipt in [by[n] for n in order if by[n]['kind']=='receipt']:
            copy_id=receipt['copy'];lineage=[copy_id];root=by[copy_id]
            while root['source']['kind']=='copy':
                root=by[root['source']['id']];lineage.insert(0,root['id'])
            doc=root['source']['id'];owner=ev['owners'][doc]
            for name in order[:pos[root['id']]]:
                e=by[name]
                if e['kind']=='owner' and e['document']==doc:owner=e['owner']
            allowed=[owner,receipt['audience']] in ev['grants']
            for name in order[:pos[receipt['id']]]:
                e=by[name]
                if e['kind'] in ('grant','revoke') and e['owner']==owner and e['audience']==receipt['audience']:allowed=e['kind']=='grant'
            if not allowed:
                bad={'order':list(order),'receipt':receipt['id'],'copy':copy_id,'lineage':lineage,'captured_owner':owner,'audience':receipt['audience'],'grant_event':None};break
        outcomes.append((order,bad))
    outcomes.sort(key=lambda x:x[0]);safe=[x for x in outcomes if x[1] is None];unsafe=[x for x in outcomes if x[1] is not None]
    classification=('inconsistent_evidence' if not outcomes else 'verified_safe' if not unsafe else 'missing_order_evidence' if safe else 'proven_violation')
    codes={'inconsistent_evidence':['inconsistent_audit_evidence'],'verified_safe':[],'missing_order_evidence':['audit_order_evidence_required'],'proven_violation':['acknowledged_delivery_not_authorized']}[classification]
    choices=[];props=sorted(b['proposals'],key=lambda p:p['id'])
    for bits in product([0,1],repeat=len(props)):
        chosen=[p for p,k in zip(props,bits) if k];extra=[x for p in chosen for x in p['before']]
        compatible=[x for x in outcomes if all(x[0].index(a)<x[0].index(c) for a,c in extra)]
        if compatible and not any(x[1] is not None for x in compatible):
            ids=[p['id'] for p in chosen];cost=sum(p['cost'] for p in chosen)
            choices.append((cost,len(ids),ids,{'proposal_ids':ids,'cost':cost,'serialization_count':len(compatible),'first_order':list(compatible[0][0])}))
    return {'ready':bool(outcomes) and not unsafe,'classification':classification,'serialization_count':len(outcomes),'safe_count':len(safe),'unsafe_count':len(unsafe),'first_safe_order':list(safe[0][0]) if safe else None,'first_unsafe':unsafe[0][1] if unsafe else None,'owner_request':min(choices,key=lambda x:x[:3])[3] if choices else None,'blocker_codes':codes}
