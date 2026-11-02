"""Cartesian oracle: recompute every resource at every time, without DFS vectors."""
import itertools,copy

def authority(b):
 visible=[x for x in b['routes'] if x['known']<=b['as_of']]
 for x,y in itertools.combinations(visible,2):
  if (x['id'],x['revision'])==(y['id'],y['revision']) and x!=y:raise ValueError('conflict')
 active=[]
 for name in sorted(set(x['id'] for x in visible)):
  signed=[x for x in visible if x['id']==name and x['signed']]
  if signed:
   row=max(signed,key=lambda x:x['revision'])
   if not row['void']:active.append(row)
 return active

def solve(b,routes,fc,pc,phases=None):
 obs=sorted(b['obligations'],key=lambda o:o['id'])
 days=sorted({d for o in obs for d in [o['pay_day'],o['repaid_day']]}|{d for r in routes for w in r['windows'] for d in [w['from_day'],w['until_day']]})
 best=None;winner=None
 for plan in itertools.product(*[[None]+[r for r in routes if r['obligation']==o['id']] for o in obs]):
  usage={'days':days,'facilities':{f:[] for f in fc},'collateral':{p:[] for p in pc}};valid=True
  for d in days:
   for f in fc:
    n=sum(o['cents'] for o,r in zip(obs,plan) if r and r['facility']==f and o['pay_day']<=d<o['repaid_day']);usage['facilities'][f].append(n)
    if n>fc[f]:valid=False
   for p in pc:
    n=sum(r['pledge_cents'] for r in plan if r for w in r['windows'] if w['pool']==p and w['from_day']<=d<w['until_day']);usage['collateral'][p].append(n)
    if (phases is None or (0 if d<10 else 1 if d<20 else 2) in phases) and n>pc[p]:valid=False
   if not valid:break
  if not valid:continue
  score=(-sum(o['cents'] for o,r in zip(obs,plan) if r),-sum(r is not None for r in plan),tuple(r['id'] if r else '~' for r in plan))
  if best is None or score<best:
   best=score;winner={'funded_cents':-score[0],'assignment':[{'obligation':o['id'],'route':r['id'],'facility':r['facility']} for o,r in zip(obs,plan) if r],'unfunded':[o['id'] for o,r in zip(obs,plan) if not r],'usage':usage}
 return winner

def oracle(b):
 rs=authority(b);fc={x['id']:x['cap'] for x in b['facilities']};pc={x['id']:x['cap'] for x in b['collateral']};cur=solve(b,rs,fc,pc)
 ps=sorted(b['proposals'],key=lambda p:p['id']);candidates=[]
 for size in range(len(ps)+1):
  for chosen in itertools.combinations(ps,size):
   fs=fc.copy();cs=pc.copy();routes=list(rs)
   for p in chosen:
    for k,v in p['facility_delta'].items():fs[k]+=v
    for k,v in p['collateral_delta'].items():cs[k]+=v
    routes+=p['routes']
   full=solve(b,routes,fs,cs)
   if not full['unfunded']:candidates.append((sum(p['cost'] for p in chosen),size,[p['id'] for p in chosen],full['assignment']))
 owner=None
 if candidates:
  cost,_,ids,a=min(candidates);owner=dict(cost=cost,proposals=ids,assignment=a)
 return dict(requested_cents=sum(o['cents'] for o in b['obligations']),complete=not cur['unfunded'],eligible_routes={o['id']:sorted(r['id'] for r in rs if r['obligation']==o['id']) for o in b['obligations']},owner_review=owner,**cur)
