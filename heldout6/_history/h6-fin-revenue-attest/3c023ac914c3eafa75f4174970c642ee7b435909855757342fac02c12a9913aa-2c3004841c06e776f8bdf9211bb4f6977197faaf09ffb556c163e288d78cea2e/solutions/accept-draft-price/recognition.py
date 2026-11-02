"""Signed evidence, immutable opening ledger, and exact cumulative catch-up."""
import copy,itertools,json,sys

def authority(b):
 result={}
 for kind in ['terms','receipts','postings']:
  seen={};selected={}
  for r in b[kind]:
   if r['known']>b['as_of']:continue
   key=r['id'],r['revision']
   if key in seen and seen[key]!=r:raise ValueError('conflicting visible evidence')
   seen[key]=r
   effective=(r['effective_period']<=b['period'] if kind=='terms' else r['period']<b['period'] if kind=='postings' else r['period']<=b['period'])
   if effective and (r['id'] not in selected or r['revision']>selected[r['id']]['revision']):selected[r['id']]=r
  rows=[{k:copy.deepcopy(v) for k,v in r.items() if k not in ('revision','known','signed','void')} for r in selected.values() if not r['void']]
  for r in rows:
   if 'eligible' in r:r['eligible'].sort()
  result[kind]=sorted(rows,key=lambda r:r['id'])
 return result

def enumerate_attributions(a,target):
 terms={t['id']:t for t in a['terms']};receipts=a['receipts'];postings=a['postings'];frozen={p['receipt']:p['obligation'] for p in postings};opening=sum(p['booked_cents'] for p in postings);opening_by={o:sum(p['booked_cents'] for p in postings if p['obligation']==o) for o in terms}
 choices=[[frozen[r['id']]] if r['id'] in frozen else r['eligible'] for r in receipts];totals=set();count=0;best=None;chosen=None
 for vector in itertools.product(*choices):
  units={o:0 for o in terms}
  for r,o in zip(receipts,vector):units[o]+=r['units']
  if any(units[o]>t['required_units'] for o,t in terms.items()):continue
  lines=[]
  for o,t in sorted(terms.items()):
   p,q,u=t['price_cents'],t['required_units'],units[o];cents=(2*p*u+q)//(2*q)
   lines.append(dict(id=o,units=u,required_units=q,price_cents=p,cumulative_cents=cents,opening_cents=opening_by[o],period_cents=cents-opening_by[o]))
  cumulative=sum(r['cumulative_cents'] for r in lines);period=cumulative-opening;totals.add(period);count+=1;key=(abs(period-target),period,vector)
  if best is None or key<best:
   best=key;chosen=dict(period_cents=period,cumulative_cents=cumulative,assignment=[dict(receipt=r['id'],obligation=o) for r,o in zip(receipts,vector)],lines=lines)
 return dict(opening_cents=opening,requested_period_cents=target,requested_cumulative_cents=target+opening,legal_assignments=count,attainable_period_cents=sorted(totals),complete=target in totals,chosen=chosen)

def analyze(b):
 a=authority(b);current=enumerate_attributions(a,b['requested_period_cents']);ps=sorted(b['proposals'],key=lambda p:p['id']);owner=None
 subsets=[tuple(ps[i] for i in range(len(ps)) if mask>>i&1) for mask in range(1<<len(ps))];subsets.sort(key=lambda rows:(sum(p['cost'] for p in rows),len(rows),[p['id'] for p in rows]))
 for chosen in subsets:
  alt=copy.deepcopy(a);target=b['requested_period_cents']
  for p in chosen:
   updates={r['id']:r for r in p['terms']}
   for t in alt['terms']:
    if t['id'] in updates:t.update(updates[t['id']])
   if p['requested_period_cents'] is not None:target=p['requested_period_cents']
  result=enumerate_attributions(alt,target)
  if result['complete']:
   owner=dict(cost=sum(p['cost'] for p in chosen),proposals=[p['id'] for p in chosen],requested_period_cents=target,chosen=result['chosen']);break
 return dict(**current,authority=a,owner_review=owner)

if __name__=='__main__':print(json.dumps(analyze(json.load(open(sys.argv[1]))),sort_keys=True))
