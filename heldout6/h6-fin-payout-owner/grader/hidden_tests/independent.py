"""Independent tuple-state graph oracle with a priority queue of whole action histories."""
import copy,heapq,itertools

def resolve(b):
 result={}
 for kind in ['owners','payouts','leases']:
  rows=[r for r in b[kind] if r['known']<=b['as_of']]
  for x,y in itertools.combinations(rows,2):
   if (x['id'],x['revision'])==(y['id'],y['revision']) and x!=y:raise ValueError('conflict')
  selected=[]
  for name in sorted(set(r['id'] for r in rows)):
   signed=[r for r in rows if r['id']==name and r['signed']]
   if not signed:continue
   r=max(signed,key=lambda r:r['revision'])
   if not r['void']:selected.append({k:(sorted(v) if isinstance(v,list) else v) for k,v in r.items() if k not in ['revision','known','signed','void']})
  result[kind]={r['id']:r['wallet'] for r in selected} if kind=='owners' else selected
 return result

def scan(wallets,a):
 jobs={r['id']:r for r in a['payouts']};loans={r['id']:r for r in a['leases']};names=sorted(jobs);owner=a['owners'];initial=tuple([0]*len(names));queue=[(0,(),initial,'')];seen={};cash_by={}
 def cash(state,loan):
  balances={w['id']:w['balance'] for w in wallets}
  for name,status in zip(names,state):
   r=jobs[name]
   if status>=1:balances[owner[r['source_owner']]]-=r['cents']
   if status==2:balances[owner[r['destination_owner']]]+=r['cents']
  if loan:balances[owner[loans[loan]['owner']]]+=loans[loan]['cents']
  return balances
 while queue:
  length,path,statuses,active=heapq.heappop(queue);state=(statuses,active)
  if state in seen:continue
  seen[state]=path;balances=cash(statuses,active);cash_by[state]=balances;states=dict(zip(names,statuses));successors=[]
  for i,name in enumerate(names):
   row=jobs[name];status=statuses[i];updated=list(statuses)
   if status==0 and balances[owner[row['source_owner']]]>=row['cents']:
    updated[i]=1;successors.append(('dispatch:'+name,tuple(updated),active))
   if status==1 and all(states[p]>=1 for p in row['receipt_after']):
    updated[i]=2;successors.append(('receipt:'+name,tuple(updated),active))
  if active:
   row=loans[active]
   if balances[owner[row['owner']]]>=row['cents'] and all(states[p]==2 for p in row['release_after']):successors.append(('repay:'+active,statuses,''))
  else:
   for name,row in loans.items():
    if all(states[p]==2 for p in row['activate_after']):successors.append(('draw:'+name,statuses,name))
  for action,ss,ll in successors:
   if (ss,ll) not in seen:heapq.heappush(queue,(length+1,path+(action,),ss,ll))
 def rank(state):
  status,loan=state;received=[name for name,s in zip(names,status) if s==2]
  return (-int(all(s==2 for s in status) and not loan),-sum(jobs[n]['cents'] for n in received),-len(received),len(seen[state]),seen[state])
 chosen=min(seen,key=rank);status,loan=chosen;received=[name for name,s in zip(names,status) if s==2]
 return dict(requested_cents=sum(r['cents'] for r in jobs.values()),settled_cents=sum(jobs[n]['cents'] for n in received),complete=all(s==2 for s in status) and not loan,settled=received,active_lease=loan or None,final_balances=cash_by[chosen],plan=list(seen[chosen]),reachable_states=len(seen))

def oracle(b):
 a=resolve(b);cur=scan(b['wallets'],a);candidates=[]
 for size in range(len(b['proposals'])+1):
  for ps in itertools.combinations(b['proposals'],size):
   alt=copy.deepcopy(a)
   for p in ps:
    for r in p['owners']:alt['owners'][r['id']]=r['wallet']
    for k in ['payouts','leases']:
     replacements={r['id']:r for r in p[k]};alt[k]=[copy.deepcopy(replacements.get(r['id'],r)) for r in alt[k]]
   check=scan(b['wallets'],alt)
   if check['complete']:candidates.append((sum(p['cost'] for p in ps),len(ps),sorted(p['id'] for p in ps),check['plan']))
 owner=None
 if candidates:
  cost,_,ids,plan=min(candidates);owner=dict(cost=cost,proposals=ids,plan=plan)
 return dict(**cur,authority=a,owner_review=owner)
