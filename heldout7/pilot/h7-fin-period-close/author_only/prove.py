"""Canonical author proof: replay current receipts, then enumerate whole-capture merchant attributions."""
from pathlib import Path
import json,time,itertools
from collections import defaultdict
ROOT=Path(__file__).parent

def reconstruct(bundle):
    by_revision={}
    for row in bundle['processor_deliveries']:
        if row['known']>bundle['as_of']:continue
        key=row['kind'],row['id'],row['revision']
        payload={k:v for k,v in row.items() if k!='event_id'}
        if key in by_revision and by_revision[key]!=payload:raise ValueError('inconsistent redelivery')
        by_revision[key]=payload
    current={}
    for (kind,identity,rev),row in by_revision.items():
        if row['final'] and (kind,identity) not in current or row['final'] and rev>current[kind,identity]['revision']:
            current[kind,identity]=row
    captures={identity:row for (kind,identity),row in current.items() if kind=='capture'}
    refunds=defaultdict(int)
    for (kind,identity),row in current.items():
        if kind=='refund':assert row['capture'] in captures;refunds[row['capture']]+=row['amount_cents']
    ids=sorted(captures);gross=[captures[i]['amount_cents'] for i in ids];refund=[refunds[i] for i in ids]
    frozen={p['capture']:p['merchant'] for p in bundle['posted_erp_journal'] if p['signed'] and p['closed']}
    totals=bundle['bank_batch_totals'];assert [sum(gross),sum(refund),sum(gross)-sum(refund)]==[totals['gross_cents'],totals['refund_cents'],totals['net_cents']]
    return ids,gross,refund,frozen


def enumerate_rollups(ids,gross,refund,frozen):
    states={(0,0,0,0):(1,())};sizes=[]
    for identity,g,r in zip(ids,gross,refund):
        following={}
        for before,(count,assignment) in states.items():
            for merchant in [frozen[identity]] if identity in frozen else ['A','B','C']:
                after=list(before)
                if merchant!='C':j=0 if merchant=='A' else 2;after[j]+=g;after[j+1]+=r
                after=tuple(after);witness=assignment+(merchant,)
                if after not in following:following[after]=(count,witness)
                else:
                    old_n,old_w=following[after];following[after]=(old_n+count,min(old_w,witness))
        states=following;sizes.append(len(states))
    return states,sizes


def main():
    started=time.perf_counter();bundle=json.loads((ROOT/'canonical_evidence.json').read_text());ids,g,r,frozen=reconstruct(bundle)
    target=tuple(bundle['signed_close_controls'][m][k] for m in ['A','B'] for k in ['gross_cents','refund_cents'])
    states,sizes=enumerate_rollups(ids,g,r,frozen);assert target not in states
    partial=[]
    for omitted in range(4):
        matches=[(v,n,a) for v,(n,a) in states.items() if all(v[j]==target[j] for j in range(4) if j!=omitted)]
        assert matches
        partial.append({'omitted_control':['A.gross','A.refunds','B.gross','B.refunds'][omitted],
                        'assignments':sum(n for v,n,a in matches),'witness':matches[0][2],'actual_controls':matches[0][0]})
    distances={v:sum(abs(a-b) for a,b in zip(v,target)) for v in states};best=min(distances.values())
    nearest=[{'controls':v,'assignments':states[v][0],'witness':states[v][1]} for v in sorted(states) if distances[v]==best]
    lower=(7700,2600,3200,1200);upper=(7700,2600,5600,1800)
    assert lower in states and upper in states
    assert tuple((2*a+b)//3 for a,b in zip(lower,upper))==target
    assert all((2*a+b)%3==0 for a,b in zip(lower,upper))
    owners=[]
    for released in [(),('cap-00',),('cap-01',),('cap-00','cap-01')]:
        altered={k:v for k,v in frozen.items() if k not in released};table,_=enumerate_rollups(ids,g,r,altered)
        count,witness=table.get(target,(0,None));owners.append({'requires_owner_reversal_of':released,'matches':count,'witness':witness})
    old=list(r);old[2]+=100;old[4]-=100;table,_=enumerate_rollups(ids,g,old,frozen)
    wrong_old={'matches':table.get(target,(0,None))[0],'witness':table.get(target,(0,None))[1]}
    assert wrong_old['matches']>0
    # Independent refund attribution can combine two different legal gross/refund partitions.
    gross_matches=[a for v,(n,a) in states.items() if v[0]==target[0] and v[2]==target[2]]
    refund_matches=[a for v,(n,a) in states.items() if v[1]==target[1] and v[3]==target[3]]
    assert gross_matches and refund_matches
    result={'controls':target,'gross':g,'refunds':r,'frozen':frozen,'legal_whole_capture_assignments':sum(n for n,a in states.values()),
      'distinct_control_vectors':len(states),'distinct_DP_states_by_prefix':sizes,'full_matches':0,'proper_three_control_checks':partial,
      'nearest_control_change_l1_cents':best,'nearest_control_corrections':nearest,
      'fractional_relaxation':{'mixture':[{'weight':'2/3','controls':lower,'witness':states[lower][1]},{'weight':'1/3','controls':upper,'witness':states[upper][1]}]},
      'closed_posting_counterfactuals':owners,'incorrect_superseded_refunds':wrong_old,
      'incorrect_independent_refund_allocation':{'gross_witness':gross_matches[0],'refund_witness':refund_matches[0]},
      'elapsed_seconds':round(time.perf_counter()-started,6)}
    (ROOT/'proof_result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
