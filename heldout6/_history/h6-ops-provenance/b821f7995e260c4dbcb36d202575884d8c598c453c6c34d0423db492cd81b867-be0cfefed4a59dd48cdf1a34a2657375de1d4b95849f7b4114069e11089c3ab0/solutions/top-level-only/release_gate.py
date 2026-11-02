import copy,fnmatch,hashlib,json,sqlite3
from contextlib import contextmanager
from crypto import canonical,verify_signature
IGNORE_DEPENDENCIES=True
IGNORE_ROLLBACK=False
EARLY_TRUST_COMMIT=False
TRUST_NEW_ROOT=False

def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
@contextmanager
def tx(path):
 db=sqlite3.connect(path,timeout=30)
 try:
  db.execute('BEGIN IMMEDIATE');db.execute('CREATE TABLE IF NOT EXISTS installs(id INTEGER PRIMARY KEY,value TEXT)');yield db;db.commit()
 except Exception:db.rollback();raise
 finally:db.close()
def save(db,s):db.execute('INSERT OR REPLACE INTO installs VALUES(1,?)',(canonical(s).decode(),))
def load(db):
 row=db.execute('SELECT value FROM installs WHERE id=1').fetchone()
 if row is None:raise ValueError('uninitialized')
 return json.loads(row[0])
def summary(s):
 return dict(version=s['version'],at=s['at'],repositories={name:dict(root_version=r['root']['version'],snapshot_version=r['snapshot_version'],roles={k:v['version'] for k,v in r['roles'].items()},installed={p:dict(length=len(raw.encode()),sha256=hashlib.sha256(raw.encode()).hexdigest()) for p,raw in r['installed'].items()}) for name,r in s['repos'].items()})
def initialize(path,anchors):
 with tx(path) as db:
  row=db.execute('SELECT value FROM installs WHERE id=1').fetchone()
  if row:
   s=json.loads(row[0])
   if s['anchors']!=anchors:raise ValueError('different anchors')
  else:
   s=dict(anchors=copy.deepcopy(anchors),version=0,at=-1,repos={name:dict(root=copy.deepcopy(root),snapshot_version=0,snapshot_digest=None,roles={},installed={}) for name,root in anchors.items()},requests={});save(db,s)
  return summary(s)
def inspect(path):
 with tx(path) as db:return summary(load(db))
def threshold(e,role,keys):
 votes={sig.get('keyid') for sig in e['signatures'] if sig.get('keyid') in role['keyids'] and sig.get('keyid') in keys and verify_signature(e['signed'],sig,keys[sig['keyid']])}
 if len(votes)<role['threshold']:raise ValueError('signature threshold')
def install(path,request):
 with tx(path) as db:
  s=load(db);q=copy.deepcopy(request);rid=q['id'];payload=canonical(q).decode()
  if rid in s['requests']:
   old=s['requests'][rid]
   if old['payload']!=payload:raise ValueError('request ID conflict')
   return copy.deepcopy(old['response'])
  if q['expected_version']!=s['version']:raise ValueError('version conflict')
  at=q['at']
  if at<s['at']:raise ValueError('time rollback')
  prepared={};pins={};resolved={};visiting=set()
  def prepare(repo):
   if repo in prepared:return prepared[repo]
   if repo not in s['repos'] or repo not in q['bundles']:raise ValueError('unknown repository')
   state=s['repos'][repo];b=q['bundles'][repo];root=state['root']
   for e in b['roots']:
    new=e['signed']
    if new['type']!='root' or new['version']!=root['version']+1 or not new['not_before']<=at<new['expires']:raise ValueError('root sequence or expiry')
    if not TRUST_NEW_ROOT:threshold(e,root['roles']['root'],root['keys'])
    threshold(e,new['roles']['root'],new['keys']);root=copy.deepcopy(new)
   if not root['not_before']<=at<root['expires']:raise ValueError('expired root')
   state['root']=root;snapshot=b['snapshot'];body=snapshot['signed'];threshold(snapshot,root['roles']['snapshot'],root['keys'])
   if body['type']!='snapshot' or at>=body['expires']:raise ValueError('snapshot type or expiry')
   h=digest(body)
   if not IGNORE_ROLLBACK and (body['version']<state['snapshot_version'] or (body['version']==state['snapshot_version'] and h!=state['snapshot_digest'])):raise ValueError('snapshot rollback/equivocation')
   state['snapshot_version']=body['version'];state['snapshot_digest']=h
   prepared[repo]=(state,b,root,body)
   if EARLY_TRUST_COMMIT:save(db,s);db.commit();db.execute('BEGIN IMMEDIATE')
   return prepared[repo]
  def lookup(repo,path):
   state,b,root,snapshot=prepare(repo)
   def visit(name,authorization,stack):
    if name in stack:raise ValueError('delegation cycle')
    e=b['metadata'].get(name);pin=snapshot['meta'].get(name)
    if e is None or pin is None or len(canonical(e))!=pin['length'] or digest(e)!=pin['sha256']:raise ValueError('metadata pin')
    body=e['signed']
    if body['type']!='targets' or body['role']!=name or body['version']!=pin['version'] or at>=body['expires']:raise ValueError('role identity/expiry')
    threshold(e,authorization,root['keys']);old=state['roles'].get(name);h=digest(body)
    if not IGNORE_ROLLBACK and old and (body['version']<old['version'] or (body['version']==old['version'] and h!=old['digest'])):raise ValueError('role rollback/equivocation')
    state['roles'][name]={'version':body['version'],'digest':h}
    if path in body['targets']:return (body['targets'][path],name),False
    for delegate in body['delegations']:
     if any(fnmatch.fnmatchcase(path,pat) for pat in delegate['paths']):
      found,terminated=visit(delegate['name'],delegate,stack|{name})
      if found:return found,False
      if terminated or delegate['terminating']:return None,True
    return None,False
   found,_=visit('targets',root['roles']['targets'],set())
   if found is None:raise ValueError('unresolved target')
   return found
  def resolve(ref):
   key=(ref['repo'],ref['path']);pin=ref['sha256']
   if key in pins and pins[key]!=pin:raise ValueError('conflicting dependency pins')
   pins[key]=pin
   if key in visiting:raise ValueError('dependency cycle')
   if key in resolved:return
   visiting.add(key);info,role=lookup(*key)
   if info['sha256']!=pin:raise ValueError('requested pin mismatch')
   if not IGNORE_DEPENDENCIES:
    for dep in info['dependencies']:resolve(dep)
   state,b,root,snapshot=prepared[key[0]];raw=b['artifacts'].get(key[1])
   if raw is None or len(raw.encode())!=info['length'] or hashlib.sha256(raw.encode()).hexdigest()!=pin:raise ValueError('artifact integrity')
   state['installed'][key[1]]=raw;resolved[key]=dict(repo=key[0],path=key[1],sha256=pin,length=info['length'],role=role);visiting.remove(key)
  for ref in q['requested']:resolve(ref)
  s['version']+=1;s['at']=at;response={**summary(s),'installed':[resolved[k] for k in sorted(resolved)]};s['requests'][rid]={'payload':payload,'response':copy.deepcopy(response)};save(db,s);return response
