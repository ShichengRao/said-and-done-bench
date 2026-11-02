import json
from pathlib import Path

def read(n):return json.loads((Path('data')/n).read_text())
t=read('ticket.json');latest={}
for r in read('reservations.json'):
    if r['revision']>latest.get(r['reservation_id'],{}).get('revision',0):latest[r['reservation_id']]=r
reserved={}
for r in latest.values():
    if r['active']:reserved[r['facility']]=reserved.get(r['facility'],0)+r['cents']
approvals=read('approvals.json');signers=read('signers.json');rows=[]
for f in sorted(read('facilities.json'),key=lambda x:x['id']):
    n=reserved.get(f['id'],0);available=f['limit_cents']-n;reasons=[]
    if available<t['amount_cents']:reasons.append('capacity')
    if f['currency']!=t['currency']:reasons.append('currency')
    if f['beneficiary']!=t['beneficiary']:reasons.append('beneficiary')
    if f['expires_day']<t['settlement_day']:reasons.append('expiry')
    valid=any(a['facility']==f['id'] and a['purchase_order']==t['purchase_order'] and a['cap_cents']>=t['amount_cents'] and a['signed_day']<=t['settlement_day']<=a['valid_until'] and signers.get(a['signer'])=='treasury' for a in approvals)
    if not valid:reasons.append('approval')
    rows.append(dict(id=f['id'],reserved_cents=n,available_cents=available,rejection_codes=sorted(reasons)))
Path('audit.json').write_text(json.dumps(dict(purchase_order=t['purchase_order'],amount_cents=t['amount_cents'],facilities=rows),indent=2)+'\n')
