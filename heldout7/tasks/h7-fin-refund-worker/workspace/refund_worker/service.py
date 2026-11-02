"""Refund worker service: outbox, worker leases, provider truth and compensation (docs/worker.md).

Reservations, expiry, replay and snapshots are in production use. The worker
paths (dispatch, cancel, abandon, receipts) are an unfinished port.
"""
import copy,json,sqlite3
from contextlib import contextmanager

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
@contextmanager
def tx(path):
 db=sqlite3.connect(path,timeout=30)
 try:
  db.execute('BEGIN IMMEDIATE');db.execute('CREATE TABLE IF NOT EXISTS refunds(id INTEGER PRIMARY KEY,value TEXT)');yield db;db.commit()
 except Exception:db.rollback();raise
 finally:db.close()
def save(db,s):db.execute('INSERT OR REPLACE INTO refunds VALUES(1,?)',(canonical(s),))
def load(db):
 row=db.execute('SELECT value FROM refunds WHERE id=1').fetchone()
 if row is None:raise ValueError('uninitialized')
 return json.loads(row[0])
def operation_id(refund,kind):return kind+'/'+refund
def new_operation(refund,kind):return dict(id=operation_id(refund,kind),refund=refund,kind=kind,started=False,attempt=0,lease=None,observation='none')
def status(s,r):
 orig=s['outbox'][operation_id(r['id'],'refund')];comp=s['outbox'].get(operation_id(r['id'],'compensation'))
 if orig['observation']=='succeeded':
  if not r['cancel_requested']:return 'succeeded'
  if comp and comp['observation']=='succeeded':return 'compensated'
  if comp and comp['observation']=='failed':return 'compensation_failed'
  return 'compensating'
 if orig['observation']=='failed':return 'cancelled' if r['cancel_requested'] else 'failed'
 if orig['started']:return 'cancel_pending' if r['cancel_requested'] else 'inflight'
 if r.get('expired'):return 'expired'
 if r['cancel_requested']:return 'cancelled'
 return 'held'
def refund_view(s,r):
 out={k:copy.deepcopy(v) for k,v in r.items() if k!='expired'};out['status']=status(s,r);return out
def balances(s):
 net={k:0 for k in s['captures']};held={k:0 for k in s['captures']}
 for r in s['refunds'].values():
  orig=s['outbox'][operation_id(r['id'],'refund')];comp=s['outbox'].get(operation_id(r['id'],'compensation'));compensated=comp and (comp['observation']=='succeeded')
  if orig['observation']=='succeeded' and not compensated:
   for a in r['allocations']:net[a['capture']]+=a['cents']
  elif orig['observation'] not in ('succeeded','failed') and not r['cancel_requested']:
   for a in r['allocations']:held[a['capture']]+=a['cents']
 return net,held
def view(s):
 net,held=balances(s);captures=[{**copy.deepcopy(c),'refunded_cents':net[k],'held_cents':held[k],'available_cents':c['captured_cents']-net[k]-held[k]} for k,c in sorted(s['captures'].items())]
 return dict(clock=s['clock'],captures=captures,refunds=[refund_view(s,s['refunds'][k]) for k in sorted(s['refunds'])],provider_operations=[copy.deepcopy(s['outbox'][k]) for k in sorted(s['outbox'])],receipts=[{'id':k,**copy.deepcopy(v)} for k,v in sorted(s['receipts'].items())],history=copy.deepcopy(s['history']))
def initialize(path,captures):
 normalized=sorted(copy.deepcopy(captures),key=lambda c:c['id'])
 with tx(path) as db:
  row=db.execute('SELECT value FROM refunds WHERE id=1').fetchone()
  if row:
   s=json.loads(row[0])
   if s['anchor']!=normalized:raise ValueError('different captures')
  else:
   s=dict(anchor=normalized,clock=0,captures={c['id']:c for c in normalized},refunds={},outbox={},receipts={},requests={},history=[]);save(db,s)
  return view(s)
def snapshot(path):
 with tx(path) as db:return view(load(db))
def apply(path,command):
 with tx(path) as db:
  s=load(db);q=copy.deepcopy(command);rid=q['operation_id'];payload=canonical(q)
  if rid in s['requests']:
   old=s['requests'][rid]
   if old['payload']!=payload:raise ValueError('operation conflict')
   return copy.deepcopy(old['response'])
  if q['at']<s['clock']:raise ValueError('time rollback')
  for r in s['refunds'].values():
   if status(s,r)=='held' and r['expires']<=q['at']:r['expired']=True;r['cancel_requested']=True;r['version']+=1
  kind=q['kind'];r=None;op=None
  if kind=='reserve':
   if q['refund'] in s['refunds'] or q['until']<=q['at'] or any(c not in s['captures'] for c in q['candidates']):raise ValueError('invalid reservation')
   net,held=balances(s);remaining=q['cents'];alloc=[];expires=q['until']
   for cid in q['candidates']:
    c=s['captures'][cid]
    if c['merchant']!=q['merchant'] or c['currency']!=q['currency'] or c['refund_until']<=q['at']:continue
    amount=min(remaining,c['captured_cents']-net[cid]-held[cid])
    if amount>0:alloc.append(dict(capture=cid,cents=amount));remaining-=amount;expires=min(expires,c['refund_until'])
   if remaining:result='unavailable'
   else:
    r=dict(id=q['refund'],merchant=q['merchant'],currency=q['currency'],cents=q['cents'],expires=expires,version=1,cancel_requested=False,allocations=alloc,expired=False);s['refunds'][r['id']]=r;op=new_operation(r['id'],'refund');s['outbox'][op['id']]=op;result='reserved'
  elif kind in ('dispatch','cancel'):
   r=s['refunds'].get(q['refund'])
   if r is None or r['version']!=q['expected_version']:raise ValueError('refund version')
   if kind=='cancel':
    if status(s,r)=='expired':raise ValueError('expired refund')
    r['cancel_requested']=True;orig=s['outbox'][operation_id(r['id'],'refund')]
    if orig['observation']=='succeeded':s['outbox'].setdefault(operation_id(r['id'],'compensation'),new_operation(r['id'],'compensation'))
    op=s['outbox'].get(operation_id(r['id'],'compensation'),orig);result='cancel_requested'
   else:
    op=s['outbox'].get(operation_id(r['id'],q['provider_kind']))
    if op is None or op['observation'] in ('succeeded','failed') or q['until']<=q['at'] or (op['lease'] is not None and op['lease']['until']>q['at']):raise ValueError('not dispatchable')
    if op['kind']=='refund' and not op['started'] and r['cancel_requested']:raise ValueError('cancelled before dispatch')
    op['started']=True;op['attempt']+=1
    if op['attempt']>1:op['id']=operation_id(r['id'],op['kind'])+'-'+str(op['attempt'])
    op['lease']=dict(token=op['id']+'/'+str(op['attempt']),worker=q['worker'],until=q['until']);result='dispatched'
   r['version']+=1
  elif kind=='abandon':
   op=s['outbox'].get(q['provider_operation'])
   if op is None or op['lease'] is None or op['lease']['token']!=q['lease_token'] or op['lease']['until']<=q['at']:raise ValueError('stale lease')
   r=s['refunds'][op['refund']];op['lease']=None;r['version']+=1;result='abandoned'
  elif kind=='receipt':
   op=s['outbox'].get(q['provider_operation'])
   if op is None or not op['started'] or q['result'] not in ('accepted','retryable','succeeded','failed'):raise ValueError('unknown provider operation')
   r=s['refunds'][op['refund']];receipt=dict(provider_operation=q['provider_operation'],result=q['result']);old=s['receipts'].get(q['receipt_id'])
   if old is not None:
    if old!=receipt:raise ValueError('receipt conflict')
    result='receipt_replayed'
   else:
    observed=op['observation'];new=q['result']
    if observed in ('succeeded','failed') and new in ('succeeded','failed') and observed!=new:raise ValueError('terminal provider conflict')
    s['receipts'][q['receipt_id']]=receipt
    if op['lease'] is None or op['lease']['until']<=q['at']:result='receipt_ignored'  # stale worker
    elif observed in ('succeeded','failed') and new in ('accepted','retryable'):result='receipt_ignored'
    else:
     if new in ('succeeded','failed'):op['observation']=new;op['lease']=None
     elif new=='accepted' or observed=='none':op['observation']=new
     result='received'
    # TODO: compensation when a cancelled refund turns out to have succeeded
   r['version']+=1
  elif kind=='tick':result='ticked'
  else:raise ValueError('unknown kind')
  s['clock']=q['at'];response=dict(operation_id=rid,result=result,refund=refund_view(s,r) if r else None,provider_operation=copy.deepcopy(op));s['requests'][rid]=dict(payload=payload,response=copy.deepcopy(response));s['history'].append(copy.deepcopy(response));save(db,s);return response
