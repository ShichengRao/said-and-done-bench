import copy,hashlib,json,sqlite3
from contextlib import contextmanager
SKIP_CLOSURE=False
IGNORE_ABORT=True
EARLY_CHECKPOINT=False
IGNORE_PARENTS=False

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
@contextmanager
def transaction(path):
 db=sqlite3.connect(path,timeout=30)
 try:
  db.execute('BEGIN IMMEDIATE');db.execute('CREATE TABLE IF NOT EXISTS recovery(id INTEGER PRIMARY KEY,value TEXT NOT NULL)');yield db;db.commit()
 except Exception:db.rollback();raise
 finally:db.close()
def load(db):
 row=db.execute('SELECT value FROM recovery WHERE id=1').fetchone()
 if row is None:raise ValueError('uninitialized')
 return json.loads(row[0])
def save(db,s):db.execute('INSERT OR REPLACE INTO recovery VALUES(1,?)',(canonical(s),))
def summary(s):return {k:copy.deepcopy(s[k]) for k in ('version','frontier','values','processed')}
def initialize(path,snapshot):
 with transaction(path) as db:
  row=db.execute('SELECT value FROM recovery WHERE id=1').fetchone()
  if row:
   s=json.loads(row[0])
   if s['anchor']!=snapshot:raise ValueError('different snapshot')
  else:
   s=dict(anchor=copy.deepcopy(snapshot),version=0,frontier=copy.deepcopy(snapshot['frontier']),values=copy.deepcopy(snapshot['values']),processed={t:'commit' for t in snapshot['applied']},events={},decisions={},requests={});save(db,s)
  return summary(s)
def inspect(path):
 with transaction(path) as db:return summary(load(db))
def replay(s,op,payload,expected):
 if op in s['requests']:
  old=s['requests'][op]
  if old['payload']!=payload:raise ValueError('request ID conflict')
  return copy.deepcopy(old['response'])
 if expected!=s['version']:raise ValueError('version conflict')
def finish(db,s,op,payload,extra):
 s['version']+=1;response={**summary(s),**extra};s['requests'][op]={'payload':payload,'response':copy.deepcopy(response)};save(db,s);return response
def ingest(path,request_id,expected_version,batch):
 payload=canonical(['ingest',expected_version,batch])
 with transaction(path) as db:
  s=load(db);old=replay(s,request_id,payload,expected_version)
  if old is not None:return old
  for e in batch['events']:
   shard=e['shard'];lsn=e['lsn'];key=shard+':'+str(lsn)
   if shard not in s['frontier'] or not isinstance(lsn,int) or isinstance(lsn,bool) or lsn<=s['anchor']['frontier'][shard] or e['ordinal']<0 or e['txid'] in s['anchor']['applied']:raise ValueError('invalid event coordinate')
   if key in s['events'] and s['events'][key]!=e:raise ValueError('event conflict')
   s['events'][key]=copy.deepcopy(e)
  for d in batch['decisions']:
   if d['outcome'] not in ('commit','abort') or not d['parts'] or d['txid'] in s['anchor']['applied'] or len(set(d['parents']))!=len(d['parents']):raise ValueError('invalid decision')
   for shard,p in d['parts'].items():
    if shard not in s['frontier'] or not p['lsns'] or p['lsns']!=sorted(set(p['lsns'])) or min(p['lsns'])<=s['anchor']['frontier'][shard]:raise ValueError('invalid manifest')
   if d['txid'] in s['decisions'] and s['decisions'][d['txid']]!=d:raise ValueError('decision conflict')
   s['decisions'][d['txid']]=copy.deepcopy(d)
  return finish(db,s,request_id,payload,{'ingested':True})
def advance(path,request_id,expected_version,target):
 payload=canonical(['advance',expected_version,target])
 with transaction(path) as db:
  s=load(db);old=replay(s,request_id,payload,expected_version)
  if old is not None:return old
  if set(target)!=set(s['frontier']) or any(not isinstance(v,int) or isinstance(v,bool) or v<s['frontier'][k] for k,v in target.items()):raise ValueError('invalid frontier')
  rows=[];edges={}
  for shard in sorted(target):
   previous=None
   for lsn in range(s['frontier'][shard]+1,target[shard]+1):
    e=s['events'].get(shard+':'+str(lsn))
    if e is None:raise ValueError('missing event')
    rows.append(e);t=e['txid'];edges.setdefault(t,set())
    if previous is not None and previous!=t:edges[t].add(previous)
    previous=t
  chosen={e['txid'] for e in rows};bytx={t:[e for e in rows if e['txid']==t] for t in chosen}
  for t in sorted(chosen):
   if t in s['processed'] or t not in s['decisions']:raise ValueError('missing or repeated decision')
   d=s['decisions'][t];allrows=[]
   for shard,p in d['parts'].items():
    part=[]
    for lsn in p['lsns']:
     e=s['events'].get(shard+':'+str(lsn))
     if e is None or e['txid']!=t:raise ValueError('manifest event missing')
     if not SKIP_CLOSURE and not s['frontier'][shard]<lsn<=target[shard]:raise ValueError('transaction crosses requested cut')
     part.append(e)
    if digest(part)!=p['sha256']:raise ValueError('seal mismatch')
    allrows.extend(part)
   allbuffer=[e for e in s['events'].values() if e['txid']==t]
   if sorted(allbuffer,key=lambda e:(e['shard'],e['lsn']))!=sorted(allrows,key=lambda e:(e['shard'],e['lsn'])):raise ValueError('unsealed transaction event')
   if sorted(e['ordinal'] for e in allrows)!=list(range(len(allrows))):raise ValueError('transaction ordinals')
   if not SKIP_CLOSURE and len(bytx[t])!=len(allrows):raise ValueError('incomplete cut')
   if not IGNORE_PARENTS:
    for parent in d['parents']:
     if s['processed'].get(parent)=='commit':continue
     if parent not in chosen or s['decisions'].get(parent,{}).get('outcome')!='commit':raise ValueError('uncommitted parent')
     edges[t].add(parent)
  order=[];pending=set(chosen)
  while pending:
   ready=sorted(t for t in pending if not edges[t]&pending)
   if not ready:raise ValueError('cyclic serialization')
   t=ready[0];pending.remove(t);order.append(t)
  for t in order:
   d=s['decisions'][t]
   if d['outcome']=='commit' or IGNORE_ABORT:
    for e in sorted(bytx[t],key=lambda e:e['ordinal']):
     state=s['values'][e['shard']]
     if state.get(e['key'])!=e['before']:raise ValueError('before-image conflict')
     if e['after'] is None:state.pop(e['key'],None)
     else:state[e['key']]=e['after']
   s['processed'][t]=d['outcome']
   if EARLY_CHECKPOINT:save(db,s);db.commit();db.execute('BEGIN IMMEDIATE')
  s['frontier']=copy.deepcopy(target)
  return finish(db,s,request_id,payload,{'order':order})
