import copy,itertools,json,sqlite3
from contextlib import contextmanager
DISPATCH_IS_SUCCESS=False
CHECK_ONLY_ALL_SUCCESS=False
STALE_APPLIES=False
REQUEST_ID_ONLY=True
CHECK_COMPLETION=True
IGNORE_EXISTING_PENDING=False

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
@contextmanager
def tx(path):
 db=sqlite3.connect(path,timeout=30)
 try:
  db.execute('BEGIN IMMEDIATE');db.execute('CREATE TABLE IF NOT EXISTS control(id INTEGER PRIMARY KEY,value TEXT)');yield db;db.commit()
 except Exception:db.rollback();raise
 finally:db.close()
def load(db):
 row=db.execute('SELECT value FROM control WHERE id=1').fetchone()
 if row is None:raise ValueError('uninitialized')
 return json.loads(row[0])
def save(db,s):db.execute('INSERT OR REPLACE INTO control VALUES(1,?)',(canonical(s),))
def summary(s):return {k:copy.deepcopy(s[k]) for k in ('version','epoch','observed','pending','done','target')}
def initialize(path,configuration):
 with tx(path) as db:
  row=db.execute('SELECT value FROM control WHERE id=1').fetchone()
  if row:
   s=json.loads(row[0])
   if s['configuration']!=configuration:raise ValueError('different configuration')
  else:
   s=dict(configuration=copy.deepcopy(configuration),version=0,epoch=0,observed=copy.deepcopy(configuration['initial']),pending={},done=[],target=None,actions={},attempts={},settled={},requests={})
   if not safe(s,s['observed']):raise ValueError('unsafe initial state')
   save(db,s)
  return summary(s)
def inspect(path):
 with tx(path) as db:return summary(load(db))
def safe(s,observed,reserved=()):
 c=s['configuration'];usage={rack:0 for rack in c['rack_capacity']};counts={svc:0 for svc in c['services']};zones={svc:set() for svc in c['services']}
 if set(observed)!=set(c['nodes']):return False
 for node,value in observed.items():
  if value is None:continue
  if value['service'] not in c['services']:return False
  spec=c['services'][value['service']];n=c['nodes'][node]
  if spec['size']>n['capacity']:return False
  usage[n['rack']]+=spec['size'];counts[value['service']]+=1;zones[value['service']].add(n['zone'])
 for action in reserved:
  if action['op']=='start':
   n=c['nodes'][action['node']];spec=c['services'][action['service']]
   if spec['size']>n['capacity']:return False
   usage[n['rack']]+=spec['size']
 return all(usage[r]<=limit for r,limit in c['rack_capacity'].items()) and all(counts[k]>=v['min_ready'] and len(zones[k])>=v['min_zones'] for k,v in c['services'].items())
def effect(observed,a):
 out=copy.deepcopy(observed);node=a['node']
 if node not in out:raise ValueError('unknown node')
 if a['op']=='start':
  if out[node] is not None:raise ValueError('start occupied')
  out[node]={'service':a['service'],'image':a['image']}
 elif a['op']=='stop':
  if out[node] is None:raise ValueError('stop empty')
  if out[node]!={'service':a['service'],'image':a['image']}:raise ValueError('stop identity')
  out[node]=None
 else:raise ValueError('unknown operation')
 return out
def robust(s,actions):
 if len({a['node'] for a in actions})!=len(actions):return False
 if not safe(s,s['observed'],actions):return False
 masks=[(1<<len(actions))-1] if CHECK_ONLY_ALL_SUCCESS else range(1<<len(actions))
 for mask in masks:
  obs=copy.deepcopy(s['observed'])
  try:
   for i,a in enumerate(actions):
    if mask>>i&1:obs=effect(obs,a)
  except ValueError:return False
  if not safe(s,obs):return False
 return True
def feasible(s,actions,target):
 ids=sorted(actions);todo=[(frozenset(),s['observed'])];seen=set()
 while todo:
  done,obs=todo.pop()
  if done in seen:continue
  seen.add(done)
  if len(done)==len(ids) and obs==target:return True
  for k in ids:
   a=actions[k]
   if k in done or not set(a['depends'])<=done:continue
   try:new=effect(obs,a)
   except ValueError:continue
   if safe(s,new):todo.append((done|{k},new))
 return False
def completion_preserved(s,pending):
 projected=copy.deepcopy(s['observed'])
 for action in pending:projected=effect(projected,action)
 completed=set(s['done'])|{action['id'] for action in pending}
 remaining={k:{**a,'depends':[d for d in a['depends'] if d not in completed]} for k,a in s['actions'].items() if k not in completed}
 return feasible({**s,'observed':projected},remaining,s['target'])

def apply(path,request):
 with tx(path) as db:
  s=load(db);q=copy.deepcopy(request);rid=q['id'];payload=canonical(q)
  if rid in s['requests']:
   old=s['requests'][rid]
   if not REQUEST_ID_ONLY and old['payload']!=payload:raise ValueError('request conflict')
   return copy.deepcopy(old['response'])
  if q['expected_version']!=s['version']:raise ValueError('version conflict')
  kind=q['kind'];extra={}
  if kind=='install':
   if q['epoch']<=s['epoch']:raise ValueError('epoch not newer')
   actions={a['id']:a for a in q['actions']}
   if len(actions)!=len(q['actions']) or any(set(a['depends'])-set(actions) or a['id'] in a['depends'] or a['node'] not in s['configuration']['nodes'] or a['service'] not in s['configuration']['services'] for a in actions.values()):raise ValueError('invalid action graph')
   s['observed']=copy.deepcopy(q['observed'])
   if not safe(s,s['observed']) or not safe(s,q['target']) or not feasible(s,actions,q['target']):raise ValueError('no safe complete schedule')
   s.update(epoch=q['epoch'],actions=actions,target=copy.deepcopy(q['target']),pending={},done=[],attempts={},settled={});extra['installed']=True
  elif kind=='dispatch':
   created=[];pending=[s['actions'][x['action']] for x in s['pending'].values()];selected=[]
   for k,a in sorted(s['actions'].items()):
    if len(pending)>=s['configuration']['max_inflight']:break
    if k in s['done'] or any(x['action']==k for x in s['pending'].values()) or not set(a['depends'])<=set(s['done']):continue
    considered=(selected if IGNORE_EXISTING_PENDING else pending)+[a]
    if not robust(s,considered):continue
    if CHECK_COMPLETION and not completion_preserved(s,considered):continue
    attempt=s['attempts'].get(k,0)+1;s['attempts'][k]=attempt;token=f"{s['epoch']}:{k}:{attempt}";s['pending'][token]={'action':k,'attempt':attempt};pending.append(a);selected.append(a);created.append(token)
    if DISPATCH_IS_SUCCESS:s['observed']=effect(s['observed'],a);s['done'].append(k)
   extra['created']=created
  elif kind=='receipt':
   dispositions=[]
   for receipt in q['receipts']:
    token=receipt['token'];success=receipt['success']
    if token in s['settled']:
     if s['settled'][token]!=success:raise ValueError('conflicting receipt')
     dispositions.append({'token':token,'disposition':'replayed'});continue
    if token not in s['pending']:
     if STALE_APPLIES:
      parts=token.split(':')
      if len(parts)==3 and parts[1] in s['actions'] and success:s['observed']=effect(s['observed'],s['actions'][parts[1]])
     dispositions.append({'token':token,'disposition':'stale'});continue
    entry=s['pending'].pop(token);a=s['actions'][entry['action']]
    if success:s['observed']=effect(s['observed'],a);s['done'].append(entry['action'])
    s['settled'][token]=success;dispositions.append({'token':token,'disposition':'applied' if success else 'failed'})
   s['done']=sorted(s['done']);extra['receipts']=dispositions
  else:raise ValueError('unknown request kind')
  s['version']+=1;response={**summary(s),**extra};s['requests'][rid]={'payload':payload,'response':copy.deepcopy(response)};save(db,s);return response
