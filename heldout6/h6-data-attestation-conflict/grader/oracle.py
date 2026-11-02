"""Independent oracle: literal sealed-stream shuffles and recorded-prefix facts.

No replay state is updated. Each precondition is recomputed from prior recorded
successes; all observations must agree before a receipt is classified.
"""
from itertools import product


def transform(bundle):
    evidence=bundle['evidence'];streams=evidence['streams'];flat=sum(streams,[])
    by={e['id']:e for e in flat};initial={n['id']:n for n in evidence['capabilities']}
    names=[e['id'] for e in flat]+[n['id'] for n in evidence['capabilities']]
    if len(names)!=len(set(names)):raise ValueError('duplicate identity')
    definitions={**initial,**{e['id']:e for e in flat if e['kind']=='grant'}}
    copy_ids={e['id'] for e in flat if e['kind']=='copy'}
    edges=[tuple(edge) for edge in evidence['before']]
    for node in definitions.values():
        if node['slot'] not in evidence['slots'] or (node['parent'] is not None and node['parent'] not in definitions):raise ValueError('unknown capability reference')
    for slot,row in evidence['slots'].items():
        if row['node'] is not None and (row['node'] not in initial or initial[row['node']]['slot']!=slot):raise ValueError('unknown initial capability')
    for e in flat:
        if e['kind']=='owner_cas' and e['document'] not in evidence['documents']:raise ValueError('unknown document')
        if e['kind'] in ('grant','revoke') and e['slot'] not in evidence['slots']:raise ValueError('unknown slot')
        if e['kind']=='copy':
            src=e['source']
            if src['kind']=='copy':
                if src['id'] not in copy_ids:raise ValueError('unknown source copy')
                edges.append((src['id'],e['id']))
            elif src['id'] not in evidence['documents'] or e['slot'] not in evidence['slots']:raise ValueError('unknown copy input')
        if e['kind']=='receipt':
            if e['copy'] not in copy_ids:raise ValueError('unknown receipt copy')
            edges.append((e['copy'],e['id']))
    extra=[tuple(edge) for p in bundle['proposals'] for edge in p['before']]
    if any(a not in by or b not in by for a,b in edges+extra):raise ValueError('unknown chronology event')
    def shuffles(parts):
        if not any(parts):yield ();return
        for i,part in enumerate(parts):
            if part:
                remaining=list(parts);remaining[i]=part[1:]
                for tail in shuffles(remaining):yield (part[0]['id'],)+tail
    accepted=[]
    for order in shuffles(streams):
        position={name:i for i,name in enumerate(order)}
        if any(position[a]>=position[b] for a,b in edges):continue
        def owner_at(document,at):
            writes=[by[n] for n in order[:at] if by[n]['kind']=='owner_cas' and by[n]['document']==document and by[n]['observed']]
            base=evidence['documents'][document]
            return (writes[-1]['owner'] if writes else base['owner'],base['version']+len(writes))
        def slot_at(slot,at):
            writes=[by[n] for n in order[:at] if by[n]['kind'] in ('grant','revoke') and by[n]['slot']==slot and by[n]['observed']]
            base=evidence['slots'][slot]
            current=(writes[-1]['id'] if writes[-1]['kind']=='grant' else None) if writes else base['node']
            return base['generation']+len(writes),current
        def is_live(name,at):
            if name not in definitions:return False
            if name not in initial and (not by[name]['observed'] or position[name]>=at):return False
            node=definitions[name]
            if slot_at(node['slot'],at)[1]!=name:return False
            return node['parent'] is None or is_live(node['parent'],at)
        consistent=True
        for at,name in enumerate(order):
            e=by[name];kind=e['kind']
            if kind=='owner_cas':predicate=owner_at(e['document'],at)[1]==e['expected']
            elif kind in ('grant','revoke'):
                predicate=slot_at(e['slot'],at)[0]==e['expected']
                if kind=='grant':
                    if e['parent'] is None:predicate=predicate and e['owner']==e['issuer']
                    else:
                        parent=definitions[e['parent']]
                        predicate=predicate and is_live(e['parent'],at) and parent['delegate'] and parent['audience']==e['issuer'] and parent['owner']==e['owner']
            else:continue
            if predicate!=e['observed']:consistent=False;break
        if not consistent:continue
        bad=None
        for receipt in (by[n] for n in order if by[n]['kind']=='receipt'):
            name=receipt['copy'];lineage=[name];root=by[name]
            while root['source']['kind']=='copy':
                root=by[root['source']['id']];lineage.insert(0,root['id'])
            doc=root['source']['id'];owner,version=owner_at(doc,position[root['id']]);cap=slot_at(root['slot'],position[root['id']])[1]
            ancestry=[];node=cap
            while node is not None:ancestry.insert(0,node);node=definitions[node]['parent']
            reason=None;invalid=None;at=position[receipt['id']]
            if cap is None:reason='missing_capability'
            elif definitions[cap]['owner']!=owner:reason='owner_mismatch'
            elif definitions[cap]['audience']!=receipt['audience']:reason='audience_mismatch'
            else:
                for n in ancestry:
                    if slot_at(definitions[n]['slot'],at)[1]!=n:reason='stale_ancestry';invalid=n;break
            if reason:
                bad={'order':list(order),'receipt':receipt['id'],'copy':receipt['copy'],'lineage':lineage,'document':doc,'captured_owner':owner,'captured_owner_version':version,'capability':cap,'ancestry':ancestry,'audience':receipt['audience'],'reason':reason,'invalid_ancestor':invalid};break
        accepted.append((order,bad))
    accepted.sort(key=lambda row:row[0]);safe=[row for row in accepted if row[1] is None];unsafe=[row for row in accepted if row[1] is not None]
    classification='inconsistent_evidence' if not accepted else 'verified_safe' if not unsafe else 'missing_order_evidence' if safe else 'proven_violation'
    code={'inconsistent_evidence':['inconsistent_audit_evidence'],'verified_safe':[],'missing_order_evidence':['audit_order_evidence_required'],'proven_violation':['acknowledged_delivery_not_authorized']}[classification]
    requests=[];proposals=sorted(bundle['proposals'],key=lambda p:p['id'])
    for mask in product((0,1),repeat=len(proposals)):
        chosen=[p for p,bit in zip(proposals,mask) if bit]
        rows=[row for row in accepted if all(row[0].index(a)<row[0].index(b) for p in chosen for a,b in p['before'])]
        if not rows or any(bad is not None for order,bad in rows):continue
        ids=[p['id'] for p in chosen];cost=sum(p['cost'] for p in chosen)
        requests.append((cost,len(ids),ids,{'proposal_ids':ids,'cost':cost,'serialization_count':len(rows),'first_order':list(rows[0][0])}))
    return {'ready':bool(accepted) and not unsafe,'classification':classification,'serialization_count':len(accepted),'safe_count':len(safe),'unsafe_count':len(unsafe),'first_safe_order':list(safe[0][0]) if safe else None,'first_unsafe':unsafe[0][1] if unsafe else None,'owner_request':min(requests,key=lambda row:row[:3])[3] if requests else None,'blocker_codes':code}
