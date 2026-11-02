"""Independent recursive allocation oracle using Decimal half-up recognition."""
import copy,itertools
from decimal import Decimal,ROUND_HALF_UP

def resolve(b):
 out={}
 for stream in ['terms','receipts','postings']:
  visible=[r for r in b[stream] if r['known']<=b['as_of']]
  for x,y in itertools.combinations(visible,2):
   if (x['id'],x['revision'])==(y['id'],y['revision']) and x!=y:raise ValueError('conflict')
  rows=[]
  for name in sorted(set(r['id'] for r in visible)):
   eligible=[r for r in visible if r['id']==name and r['signed'] and (r['effective_period']<=b['period'] if stream=='terms' else r['period']<b['period'] if stream=='postings' else r['period']<=b['period'])]
   if not eligible:continue
   r=max(eligible,key=lambda r:r['revision'])
   if not r['void']:rows.append({k:(sorted(v) if isinstance(v,list) else v) for k,v in r.items() if k not in ['revision','known','signed','void']})
  out[stream]=rows
 return out

def solve(a,target,freeze=True):
 terms={r['id']:r for r in a['terms']};receipts=a['receipts'];opening=sum(p['booked_cents'] for p in a['postings']);pins={p['receipt']:p['obligation'] for p in a['postings']} if freeze else {};candidates=[]
 def visit(i,units,assignment):
  if i<len(receipts):
   r=receipts[i]
   for ob in ([pins[r['id']]] if r['id'] in pins else sorted(r['eligible'])):
    if units[ob]+r['units']<=terms[ob]['required_units']:
     nextunits=units.copy();nextunits[ob]+=r['units'];visit(i+1,nextunits,assignment+[dict(receipt=r['id'],obligation=ob)])
   return
  lines=[]
  for name,t in sorted(terms.items()):
   value=int((Decimal(t['price_cents'])*units[name]/t['required_units']).quantize(Decimal(1),rounding=ROUND_HALF_UP));prior=sum(p['booked_cents'] for p in a['postings'] if p['obligation']==name)
   lines.append(dict(id=name,units=units[name],required_units=t['required_units'],price_cents=t['price_cents'],cumulative_cents=value,opening_cents=prior,period_cents=value-prior))
  cumulative=sum(r['cumulative_cents'] for r in lines);candidates.append(dict(period_cents=cumulative-opening,cumulative_cents=cumulative,assignment=assignment,lines=lines))
 visit(0,{n:0 for n in terms},[])
 totals=sorted(set(c['period_cents'] for c in candidates));chosen=min(candidates,key=lambda c:(abs(c['period_cents']-target),c['period_cents'],[r['obligation'] for r in c['assignment']])) if candidates else None
 return dict(opening_cents=opening,requested_period_cents=target,requested_cumulative_cents=target+opening,legal_assignments=len(candidates),attainable_period_cents=totals,complete=target in totals,chosen=chosen)

def oracle(b):
 a=resolve(b);current=solve(a,b['requested_period_cents']);candidates=[]
 for size in range(len(b['proposals'])+1):
  for chosen in itertools.combinations(b['proposals'],size):
   alt=copy.deepcopy(a);target=b['requested_period_cents']
   for p in chosen:
    for replacement in p['terms']:
     for term in alt['terms']:
      if term['id']==replacement['id']:term.update(replacement)
    if p['requested_period_cents'] is not None:target=p['requested_period_cents']
   r=solve(alt,target)
   if r['complete']:candidates.append((sum(p['cost'] for p in chosen),size,sorted(p['id'] for p in chosen),target,r['chosen']))
 owner=None
 if candidates:
  cost,_,ids,target,chosen=min(candidates,key=lambda c:c[:3]);owner=dict(cost=cost,proposals=ids,requested_period_cents=target,chosen=chosen)
 return dict(**current,authority=a,owner_review=owner)
