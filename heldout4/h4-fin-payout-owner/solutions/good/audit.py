import json
from pathlib import Path

def read(n):return json.loads((Path('data')/n).read_text())
batch=read('ticket.json')['batch'];latest={}
for e in read('settlements.json'):
    if e['revision']>latest.get(e['event_id'],{}).get('revision',0):latest[e['event_id']]=e
net={}
for e in latest.values():
    if e['batch']==batch and not e['void']:net[e['bucket']]=net.get(e['bucket'],0)+e['cents']
buckets=read('buckets.json');merchants=read('merchants.json');atts=read('attestations.json');signers=read('signers.json')
payouts=[];unresolved=[]
for bucket,cents in sorted(net.items()):
    if cents==0:continue
    b=buckets[bucket];candidates=sorted(m['id'] for m in merchants if m['active'] and m['bank_token']==b['bank_token'] and m['currency']==b['currency'])
    valid={a['merchant_id'] for a in atts if a['batch']==batch and a['bucket']==bucket and a['approved'] and signers.get(a['signed_by'])=='finance_owner' and a['merchant_id'] in candidates}
    owner=next(iter(valid)) if len(valid)==1 else candidates[0] if not valid and len(candidates)==1 else None
    if owner:payouts.append(dict(bucket=bucket,merchant_id=owner,cents=cents))
    else:unresolved.append(dict(bucket=bucket,candidates=candidates,cents=cents))
Path('audit.json').write_text(json.dumps(dict(batch=batch,payouts=payouts,unresolved=unresolved,total_cents=sum(net.values())),indent=2)+'\n')
