"""Independent grouped-event replay and meet-in-the-middle certificate check.
Does not import prove.py or its reconstruction/enumeration functions.
"""
from pathlib import Path
from collections import defaultdict
from itertools import product
from fractions import Fraction
import json,time
ROOT=Path(__file__).parent
started=time.perf_counter()
b=json.loads((ROOT/'canonical_evidence.json').read_text())
groups=defaultdict(list)
for event in b['processor_deliveries']:
    if event['known']<=b['as_of']:groups[event['kind'],event['id']].append(event)
current={};earliest={}
for key,deliveries in groups.items():
    revisions=defaultdict(list)
    for event in deliveries:revisions[event['revision']].append(event)
    for rev,copies in revisions.items():
        semantic=[{k:v for k,v in event.items() if k!='event_id'} for event in copies]
        assert all(event==semantic[0] for event in semantic)
    accepted=sorted([v[0] for v in revisions.values() if v[0]['final']],key=lambda e:e['revision'])
    if accepted:earliest[key]=accepted[0];current[key]=accepted[-1]
ids=sorted(identity for kind,identity in current if kind=='capture')
gross={identity:current['capture',identity]['amount_cents'] for identity in ids}
refund={identity:0 for identity in ids};old_refund=dict(refund)
for (kind,identity),event in current.items():
    if kind=='refund':refund[event['capture']]+=event['amount_cents'];prior=earliest[kind,identity];old_refund[prior['capture']]+=prior['amount_cents']
frozen={e['capture']:e['merchant'] for e in b['posted_erp_journal'] if e['signed'] and e['closed']}
target=tuple(b['signed_close_controls'][m][k] for m in ('A','B') for k in ('gross_cents','refund_cents'))
assert sum(gross.values())==b['bank_batch_totals']['gross_cents'] and sum(refund.values())==b['bank_batch_totals']['refund_cents']

def contribution(assign,refunds):
    return tuple(sum((gross if dim%2==0 else refunds)[identity] for identity,m in assign.items() if m==('A' if dim<2 else 'B')) for dim in range(4))

def count_matches(fixed,refunds=refund,dimensions=(0,1,2,3),wanted=target):
    rest=[i for i in ids if i not in fixed];left,right=rest[:len(rest)//2],rest[len(rest)//2:]
    fixed_v=contribution(fixed,refunds)
    right_index={}
    for choice in product('ABC',repeat=len(right)):
        assignment=dict(zip(right,choice));full=contribution(assignment,refunds);key=tuple(full[d] for d in dimensions)
        count,witness=right_index.get(key,(0,None));right_index[key]=(count+1,assignment if witness is None else witness)
    matches=0;witness=None
    for choice in product('ABC',repeat=len(left)):
        assignment=dict(zip(left,choice));value=contribution(assignment,refunds)
        needed=tuple(wanted[d]-fixed_v[d]-value[d] for d in dimensions)
        count,other=right_index.get(needed,(0,None));matches+=count
        if count and witness is None:witness={**fixed,**assignment,**other}
    return {'matches':matches,'witness':[witness[i] for i in ids] if witness else None,'left_half_assignments':3**len(left),
            'right_half_assignments':3**len(right),'right_index_entries':len(right_index)}
base=count_matches(frozen);assert base['matches']==0
triples=[count_matches(frozen,dimensions=tuple(d for d in range(4) if d!=omitted)) for omitted in range(4)]
assert [r['matches'] for r in triples]==[1,1,1,2]
only00=count_matches({k:v for k,v in frozen.items() if k!='cap-00'})
only01=count_matches({k:v for k,v in frozen.items() if k!='cap-01'})
rebook=count_matches({**frozen,'cap-01':'C'})
assert only00['matches']==0 and only01['matches']==rebook['matches']==1
stale=count_matches(frozen,old_refund);assert stale['matches']==1
nearA=count_matches(frozen,wanted=(7700,2500,4000,1400));nearB=count_matches(frozen,wanted=(7700,2600,4000,1300))
assert nearA['matches']==nearB['matches']==1
assert all(n%100==0 for n in list(gross.values())+list(refund.values())+list(target))
primary=json.loads((ROOT/'proof_result.json').read_text());mix=primary['fractional_relaxation']['mixture'];total=[Fraction(0) for _ in range(4)]
for part in mix:
    assignment=dict(zip(ids,part['witness']));assert all(assignment[i]==m for i,m in frozen.items())
    vector=contribution(assignment,refund);assert list(vector)==part['controls']
    for j,n in enumerate(vector):total[j]+=Fraction(part['weight'])*n
assert total==list(target)
result={'independent_method':'Separate grouped revision replay; 81+81 half-assignments joined on four totals, not the primary full-vector DP.',
 'base':base,'proper_triples':triples,'release_posted_00_only':only00,'release_posted_01_only':only01,'authorized_reversal_and_rebook_01_to_C':rebook,
 'stale_refund_revision_false_close':stale,'nearest_signed_control_corrections':[nearA,nearB],'fractional_certificate_verified':True,
 'elapsed_seconds':round(time.perf_counter()-started,6)}
(ROOT/'independent_result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'base':base,'triple_counts':[r['matches'] for r in triples],'rebook_matches':rebook['matches'],'elapsed_seconds':result['elapsed_seconds']}))
