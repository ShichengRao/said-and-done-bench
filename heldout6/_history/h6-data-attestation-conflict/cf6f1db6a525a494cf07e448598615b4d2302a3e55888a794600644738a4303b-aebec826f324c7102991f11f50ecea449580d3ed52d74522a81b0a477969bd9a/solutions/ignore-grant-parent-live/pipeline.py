from copy import deepcopy
from itertools import combinations


def transform(bundle):
    evidence=bundle['evidence'];streams=evidence['streams']
    events=[e for stream in streams for e in stream];by={e['id']:e for e in events}
    initial={n['id']:n for n in evidence['capabilities']}
    if len(by)!=len(events) or len(initial)!=len(evidence['capabilities']) or set(by)&set(initial):raise ValueError('duplicate identity')
    node_ids=set(initial)|{e['id'] for e in events if e['kind']=='grant'}
    copies={e['id'] for e in events if e['kind']=='copy'}
    def check_node(n):
        if n['slot'] not in evidence['slots'] or (n['parent'] is not None and n['parent'] not in node_ids):raise ValueError('unknown capability reference')
    for n in initial.values():check_node(n)
    for name,row in evidence['slots'].items():
        if row['node'] is not None and (row['node'] not in initial or initial[row['node']]['slot']!=name):raise ValueError('unknown initial slot node')
    edges=[tuple(edge) for edge in evidence['before']]
    for e in events:
        kind=e['kind']
        if kind=='owner_cas' and e['document'] not in evidence['documents']:raise ValueError('unknown document')
        if kind in ('grant','revoke') and e['slot'] not in evidence['slots']:raise ValueError('unknown slot')
        if kind=='grant':check_node(e)
        if kind=='copy':
            src=e['source']
            if src['kind']=='document':
                if src['id'] not in evidence['documents'] or e['slot'] not in evidence['slots']:raise ValueError('unknown copy input')
            else:
                if src['id'] not in copies:raise ValueError('unknown source copy')
                edges.append((src['id'],e['id']))
        if kind=='receipt':
            if e['copy'] not in copies:raise ValueError('unknown receipt copy')
            edges.append((e['copy'],e['id']))
    if any(a not in by or b not in by for a,b in edges+[tuple(x) for p in bundle['proposals'] for x in p['before']]):raise ValueError('unknown chronology endpoint')
    predecessors={e:set() for e in by}
    for a,b in edges:predecessors[b].add(a)
    state={'documents':deepcopy(evidence['documents']),'slots':deepcopy(evidence['slots']),'nodes':deepcopy(initial),'copies':{}}
    def live(identity,s):
        if identity not in s['nodes']:return False
        n=s['nodes'][identity]
        if s['slots'][n['slot']]['node']!=identity:return False
        return n['parent'] is None or live(n['parent'],s)
    def capture(document,slot,s):
        node=s['slots'][slot]['node'];chain=[];cursor=node
        while cursor is not None:
            chain.append(cursor);cursor=s['nodes'][cursor]['parent']
        return {'document':document,'owner':s['documents'][document]['owner'],'owner_version':s['documents'][document]['version'],'capability':node,'ancestry':chain[::-1],'slot':slot}
    def step(e,s):
        kind=e['kind'];s=deepcopy(s);failure=None
        if kind in ('owner_cas','grant','revoke'):
            if kind=='owner_cas':success=s['documents'][e['document']]['version']==e['expected']
            else:
                success=s['slots'][e['slot']]['generation']==e['expected']
                if kind=='grant':
                    if e['parent'] is None:success=success and e['issuer']==e['owner']
                    else:
                        parent=s['nodes'].get(e['parent'])
                        success=success and bool(parent) and parent['delegate'] and parent['audience']==e['issuer'] and parent['owner']==e['owner']
            if e['observed']!=success:return None
            if e['observed']:
                if kind=='owner_cas':s['documents'][e['document']]={'owner':e['owner'],'version':s['documents'][e['document']]['version']+1}
                else:
                    s['slots'][e['slot']]['generation']+=1;s['slots'][e['slot']]['node']=None if kind=='revoke' else e['id']
                    if kind=='grant':s['nodes'][e['id']]={k:e[k] for k in ['id','slot','parent','owner','issuer','audience','delegate']}
        elif kind=='copy':
            src=e['source']
            if src['kind']=='document':captured=capture(src['id'],e['slot'],s);lineage=[]
            else:captured=deepcopy(s['copies'][src['id']]);lineage=captured['lineage']
            captured['lineage']=lineage+[e['id']];s['copies'][e['id']]=captured
        elif kind=='receipt':
            captured=s['copies'][e['copy']];identity=captured['capability'];reason=None;invalid=None
            if identity is None:reason='missing_capability'
            elif s['nodes'][identity]['owner']!=captured['owner']:reason='owner_mismatch'
            elif s['nodes'][identity]['audience']!=e['audience']:reason='audience_mismatch'
            elif not live(identity,s):
                reason='stale_ancestry';invalid=next(n for n in captured['ancestry'] if s['slots'][s['nodes'][n]['slot']]['node']!=n)
            if reason:failure={'receipt':e['id'],'copy':e['copy'],'lineage':captured['lineage'],'document':captured['document'],'captured_owner':captured['owner'],'captured_owner_version':captured['owner_version'],'capability':identity,'ancestry':captured['ancestry'],'audience':e['audience'],'reason':reason,'invalid_ancestor':invalid}
        return s,failure
    outcomes=[]
    def visit(indices,s,order,bad):
        if len(order)==len(events):outcomes.append((tuple(order),None if bad is None else {'order':list(order),**bad}));return
        completed=set(order)
        for i,stream in enumerate(streams):
            if indices[i]>=len(stream):continue
            e=stream[indices[i]]
            if not predecessors[e['id']]<=completed:continue
            result=step(e,s)
            if result is None:continue
            next_state,failure=result;following=list(indices);following[i]+=1
            visit(following,next_state,order+[e['id']],bad if bad is not None else failure)
    visit([0]*len(streams),state,[],None);outcomes.sort(key=lambda x:x[0])
    safe=[o for o,bad in outcomes if bad is None];unsafe=[bad for o,bad in outcomes if bad is not None]
    classification='inconsistent_evidence' if not outcomes else 'verified_safe' if not unsafe else 'missing_order_evidence' if safe else 'proven_violation'
    codes={'inconsistent_evidence':['inconsistent_audit_evidence'],'verified_safe':[],'missing_order_evidence':['audit_order_evidence_required'],'proven_violation':['acknowledged_delivery_not_authorized']}[classification]
    candidates=[];props=sorted(bundle['proposals'],key=lambda p:p['id'])
    for size in range(len(props)+1):
        for chosen in combinations(props,size):
            extra=[edge for p in chosen for edge in p['before']]
            remaining=[(order,bad) for order,bad in outcomes if all(order.index(a)<order.index(b) for a,b in extra)]
            if remaining and not any(bad is not None for order,bad in remaining):
                ids=[p['id'] for p in chosen];cost=sum(p['cost'] for p in chosen)
                candidates.append((cost,len(ids),ids,{'proposal_ids':ids,'cost':cost,'serialization_count':len(remaining),'first_order':list(remaining[0][0])}))
    return {'ready':bool(outcomes) and not unsafe,'classification':classification,'serialization_count':len(outcomes),'safe_count':len(safe),'unsafe_count':len(unsafe),'first_safe_order':list(safe[0]) if safe else None,'first_unsafe':unsafe[0] if unsafe else None,'owner_request':min(candidates,key=lambda x:x[:3])[3] if candidates else None,'blocker_codes':codes}

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
