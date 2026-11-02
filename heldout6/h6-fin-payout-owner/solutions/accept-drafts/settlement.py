"""Signed authority reconstruction and finite legal-settlement state search."""
import copy,itertools,json,sys
from collections import deque

def authority(bundle):
 result={}
 for stream in ['owners','payouts','leases']:
  seen={};selected={}
  for r in bundle[stream]:
   if r['known']>bundle['as_of']:continue
   key=r['id'],r['revision']
   if key in seen and seen[key]!=r:raise ValueError('conflicting authority delivery')
   seen[key]=r
   if (r['id'] not in selected or r['revision']>selected[r['id']]['revision']):selected[r['id']]=r
  rows=[{k:copy.deepcopy(v) for k,v in r.items() if k not in ('revision','known','signed','void')} for r in selected.values() if not r['void']]
  rows.sort(key=lambda r:r['id'])
  if stream=='owners':result[stream]={r['id']:r['wallet'] for r in rows}
  else:
   for r in rows:
    for k in ['receipt_after','activate_after','release_after']:
     if k in r:r[k]=sorted(r[k])
   result[stream]=rows
 return result

def explore(wallets,a):
 payouts=a['payouts'];leases=a['leases'];owners=a['owners'];pidx={p['id']:i for i,p in enumerate(payouts)};allmask=(1<<len(payouts))-1
 def balance(s):
  d,r,l=s;cash={w['id']:w['balance'] for w in wallets}
  for i,p in enumerate(payouts):
   if d>>i&1:cash[owners[p['source_owner']]]-=p['cents']
   if r>>i&1:cash[owners[p['destination_owner']]]+=p['cents']
  if l>=0:cash[owners[leases[l]['owner']]]+=leases[l]['cents']
  return cash
 start=(0,0,-1);paths={start:[]};queue=deque([start])
 while queue:
  state=queue.popleft();d,r,l=state;cash=balance(state);actions=[]
  for i,p in enumerate(payouts):
   if not d>>i&1 and cash[owners[p['source_owner']]]>=p['cents']:actions.append(('dispatch:'+p['id'],(d|1<<i,r,l)))
   if d>>i&1 and not r>>i&1 and all(d>>pidx[x]&1 for x in p['receipt_after']):actions.append(('receipt:'+p['id'],(d,r|1<<i,l)))
  if l<0:
   for i,q in enumerate(leases):
    if all(r>>pidx[x]&1 for x in q['activate_after']):actions.append(('draw:'+q['id'],(d,r,i)))
  else:
   q=leases[l]
   if cash[owners[q['owner']]]>=q['cents'] and all(r>>pidx[x]&1 for x in q['release_after']):actions.append(('repay:'+q['id'],(d,r,-1)))
  for action,nextstate in sorted(actions):
   if nextstate not in paths:paths[nextstate]=paths[state]+[action];queue.append(nextstate)
 def key(s):
  d,r,l=s;settled=[p for i,p in enumerate(payouts) if r>>i&1]
  return (-(r==allmask and l==-1),-sum(p['cents'] for p in settled),-len(settled),len(paths[s]),paths[s])
 state=min(paths,key=key);d,r,l=state;settled=[p['id'] for i,p in enumerate(payouts) if r>>i&1]
 return dict(requested_cents=sum(p['cents'] for p in payouts),settled_cents=sum(p['cents'] for p in payouts if p['id'] in settled),complete=r==allmask and l==-1,settled=settled,active_lease=leases[l]['id'] if l>=0 else None,final_balances=balance(state),plan=paths[state],reachable_states=len(paths))

def analyze(bundle):
 a=authority(bundle);current=explore(bundle['wallets'],a);ps=sorted(bundle['proposals'],key=lambda p:p['id']);owner=None
 subsets=[tuple(ps[i] for i in range(len(ps)) if mask>>i&1) for mask in range(1<<len(ps))]
 subsets.sort(key=lambda rows:(sum(p['cost'] for p in rows),len(rows),[p['id'] for p in rows]))
 for chosen in subsets:
  alt=copy.deepcopy(a)
  for p in chosen:
   for row in p['owners']:alt['owners'][row['id']]=row['wallet']
   for k in ['payouts','leases']:
    updates={r['id']:r for r in p[k]};alt[k]=[copy.deepcopy(updates.get(r['id'],r)) for r in alt[k]]
  result=explore(bundle['wallets'],alt)
  if result['complete']:
   owner=dict(cost=sum(p['cost'] for p in chosen),proposals=[p['id'] for p in chosen],plan=result['plan']);break
 return dict(**current,authority=a,owner_review=owner)

if __name__=='__main__':print(json.dumps(analyze(json.load(open(sys.argv[1]))),sort_keys=True))
