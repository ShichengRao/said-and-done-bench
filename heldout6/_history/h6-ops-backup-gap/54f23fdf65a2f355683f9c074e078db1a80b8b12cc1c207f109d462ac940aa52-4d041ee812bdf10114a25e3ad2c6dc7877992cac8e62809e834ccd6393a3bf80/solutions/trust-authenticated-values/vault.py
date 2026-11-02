import copy,hashlib,itertools,json,sys
TRUST_ALL_ROWS=True
RANK_QUERIES=False
IGNORE_FAULT_BUDGET=False

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def mul(a,b):
 z=0
 while b:
  if b&1:z^=a
  a<<=1
  if a&256:a^=0x11b
  b>>=1
 return z
def power(a,n):
 z=1
 while n:
  if n&1:z=mul(z,a)
  a=mul(a,a);n>>=1
 return z
def dot(a,b):
 z=0
 for x,y in zip(a,b):z^=mul(x,y)
 return z
def solve(rows,width):
 a=[list(c)+[v] for c,v in rows];pivots=[];r=0
 for col in range(width):
  k=next((i for i in range(r,len(a)) if a[i][col]),None)
  if k is None:continue
  a[r],a[k]=a[k],a[r];inv=power(a[r][col],254);a[r]=[mul(x,inv) for x in a[r]]
  for i in range(len(a)):
   if i!=r and a[i][col]:
    f=a[i][col];a[i]=[x^mul(f,y) for x,y in zip(a[i],a[r])]
  pivots.append(col);r+=1
 if any(not any(row[:width]) and row[-1] for row in a):return r,[]
 free=[i for i in range(width) if i not in pivots]
 if len(free)>1:raise ValueError('outside bounded profile')
 out=[]
 for vals in itertools.product(range(256),repeat=len(free)):
  x=[0]*width
  for i,v in zip(free,vals):x[i]=v
  for row,p in zip(a,pivots):x[p]=row[-1]^dot(row[:width],x)
  out.append(tuple(x))
 return r,out

def audit(data):
 d=copy.deepcopy(data);width=d['width'];latest={};seen={}
 for row in d['fragments']:
  key=row['id'];rev=(key,row['revision']);old=latest.get(key)
  if rev in seen and seen[rev]!=row:raise ValueError('conflicting revision')
  seen[rev]=row
  if old is None or row['revision']>old['revision']:latest[key]=row
  elif row['revision']==old['revision'] and row!=old:raise ValueError('conflicting revision')
 accepted=[];rejected=[]
 for key,r in sorted(latest.items()):
  reason= 'retired' if not r['live'] else 'scope' if (r['tenant'],r['generation'])!=(d['tenant'],d['generation']) else 'checksum' if digest({'coefficients':r['coefficients'],'value':r['value']})!=r['sha256'] else None
  if reason:rejected.append({'id':key,'reason':reason})
  else:accepted.append(r)
 rows=[(r['coefficients'],r['value']) for r in accepted];anchors=[(a['coefficients'],a['value']) for a in d['anchors']]
 n=len(rows);budget=min(d['fault_budget'],n);candidates=set()
 for omitted in itertools.combinations(range(n),0 if TRUST_ALL_ROWS else budget):
  included=[v for i,v in enumerate(rows) if i not in omitted]+anchors
  _,possible=solve(included,width)
  for x in possible:
   faults=sum(dot(c,x)!=v for c,v in rows)
   if (IGNORE_FAULT_BUDGET or faults<=budget) and all(dot(c,x)==v for c,v in anchors):candidates.add(x)
 ordered=sorted(candidates);encoded=[''.join(f'{v:02x}' for v in x) for x in ordered]
 unique=[ordered[0][i] if ordered and len({x[i] for x in ordered})==1 else None for i in range(width)]
 queries=sorted(d['owner_queries'],key=lambda q:q['id']);best=None
 if len(ordered)<=1:best={'cost':0,'queries':[]}
 else:
  for bits in range(1<<len(queries)):
   qs=[q for i,q in enumerate(queries) if bits>>i&1]
   signatures={tuple(dot(q['coefficients'],x) for q in qs) for x in ordered}
   if RANK_QUERIES:
    valid=bool(qs)
   else:valid=len(signatures)==len(ordered)
   candidate={'cost':sum(q['cost'] for q in qs),'queries':[q['id'] for q in qs]}
   if valid and (best is None or (candidate['cost'],candidate['queries'])<(best['cost'],best['queries'])):best=candidate
 blocker=None
 if len(ordered)>1:blocker={'kind':'ambiguous_restore','candidate_count':len(ordered),'owner_queries':best['queries'] if best else None}
 elif not ordered:blocker={'kind':'inconsistent_evidence','candidate_count':0,'owner_queries':None}
 return {'accepted':[r['id'] for r in accepted],'rejected':rejected,'candidate_count':len(ordered),'candidate_sha256':digest(encoded),'witnesses':encoded[:2],'unique_symbols':unique,'owner_plan':best,'certifiable':len(ordered)==1,'blocker':blocker}
if __name__=='__main__':print(json.dumps(audit(json.load(open(sys.argv[1]))),sort_keys=True))
