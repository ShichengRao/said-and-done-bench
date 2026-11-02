import copy,fnmatch,hashlib,json,sqlite3,sys
from contextlib import contextmanager
from crypto import canonical,verify_signature
TRUST_NEW_ROOT=True
IGNORE_ROLLBACK=False
IGNORE_TERMINATING=False
EARLY_ROOT_COMMIT=False

def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
@contextmanager
def transaction(path):
    db=sqlite3.connect(path,timeout=30)
    try:
        db.execute('BEGIN IMMEDIATE');db.execute('CREATE TABLE IF NOT EXISTS release_state(id INTEGER PRIMARY KEY CHECK(id=1),value TEXT NOT NULL)');yield db;db.commit()
    except Exception:db.rollback();raise
    finally:db.close()
def load(db):
    row=db.execute('SELECT value FROM release_state WHERE id=1').fetchone()
    if row is None:raise ValueError('uninitialized')
    return json.loads(row[0])
def save(db,data):db.execute('INSERT OR REPLACE INTO release_state VALUES(1,?)',(canonical(data).decode(),))
def summary(s):return dict(root_version=s['root']['version'],at=s['at'],snapshot_version=s['snapshot_version'],roles={r:x['version'] for r,x in s['roles'].items()},installed={p:dict(length=len(raw.encode()),sha256=hashlib.sha256(raw.encode()).hexdigest()) for p,raw in s['installed'].items()})
def threshold(envelope,role,keys):
    votes={sig.get('keyid') for sig in envelope['signatures'] if sig.get('keyid') in role['keyids'] and sig.get('keyid') in keys and verify_signature(envelope['signed'],sig,keys[sig['keyid']])}
    if len(votes)<role['threshold']:raise ValueError('signature threshold')
def initialize(path,root):
    with transaction(path) as db:
        try:data=load(db)
        except ValueError:
            data=dict(anchor=copy.deepcopy(root),root=copy.deepcopy(root),at=-1,snapshot_version=0,snapshot_digest=None,roles={},installed={},requests={});save(db,data)
        else:
            if data['anchor']!=root:raise ValueError('different anchor')
        return summary(data)
def inspect(path):
    with transaction(path) as db:return summary(load(db))
def verify_and_stage(path,bundle):
    with transaction(path) as db:
        state=load(db);operation=bundle['id'];payload=canonical(bundle).decode()
        if operation in state['requests']:
            previous=state['requests'][operation]
            if previous['payload']!=payload:raise ValueError('operation ID conflict')
            return copy.deepcopy(previous['response'])
        at=bundle['at']
        if at<state['at']:raise ValueError('time rollback')
        root=state['root']
        for envelope in bundle['roots']:
            candidate=envelope['signed']
            if candidate['type']!='root' or candidate['version']!=root['version']+1 or not candidate['not_before']<=at<candidate['expires']:raise ValueError('root sequence or expiry')
            if not TRUST_NEW_ROOT:threshold(envelope,root['roles']['root'],root['keys'])
            threshold(envelope,candidate['roles']['root'],candidate['keys']);root=copy.deepcopy(candidate)
        if not root['not_before']<=at<root['expires']:raise ValueError('expired root')
        state['root']=root
        if EARLY_ROOT_COMMIT:save(db,state);db.commit();db.execute('BEGIN IMMEDIATE')
        snapshot=bundle['snapshot'];body=snapshot['signed'];threshold(snapshot,root['roles']['snapshot'],root['keys'])
        if body['type']!='snapshot' or at>=body['expires']:raise ValueError('invalid snapshot')
        bodyhash=digest(body)
        if not IGNORE_ROLLBACK and (body['version']<state['snapshot_version'] or (body['version']==state['snapshot_version'] and state['snapshot_digest']!=bodyhash)):raise ValueError('snapshot rollback or equivocation')
        updates={}
        def visit(name,path,authorization,stack):
            if name in stack:raise ValueError('delegation cycle')
            envelope=bundle['metadata'].get(name);pin=body['meta'].get(name)
            if envelope is None or pin is None:raise ValueError('missing metadata')
            if len(canonical(envelope))!=pin['length'] or digest(envelope)!=pin['sha256']:raise ValueError('metadata pin')
            b=envelope['signed']
            if b['type']!='targets' or b['role']!=name or b['version']!=pin['version'] or at>=b['expires']:raise ValueError('metadata identity or expiry')
            threshold(envelope,authorization,root['keys']);old=state['roles'].get(name);h=digest(b)
            if not IGNORE_ROLLBACK and old and (b['version']<old['version'] or (b['version']==old['version'] and h!=old['digest'])):raise ValueError('role rollback or equivocation')
            updates[name]=dict(version=b['version'],digest=h)
            if path in b['targets']:return (b['targets'][path],name),False
            for delegate in b['delegations']:
                if any(fnmatch.fnmatchcase(path,pattern) for pattern in delegate['paths']):
                    found,terminated=visit(delegate['name'],path,delegate,stack|{name})
                    if found:return found,False
                    if not IGNORE_TERMINATING and (terminated or delegate['terminating']):return None,True
            return None,False
        installed=[]
        for path in sorted(bundle['requested']):
            found,_=visit('targets',path,root['roles']['targets'],set())
            if found is None or path not in bundle['artifacts']:raise ValueError('unresolved artifact')
            info,role=found;raw=bundle['artifacts'][path];rawbytes=raw.encode()
            if len(rawbytes)!=info['length'] or hashlib.sha256(rawbytes).hexdigest()!=info['sha256']:raise ValueError('artifact integrity')
            state['installed'][path]=raw;installed.append(dict(path=path,length=info['length'],sha256=info['sha256'],role=role))
        state['roles'].update(updates);state.update(at=at,snapshot_version=body['version'],snapshot_digest=bodyhash)
        response=dict(root_version=root['version'],snapshot_version=body['version'],installed=installed);state['requests'][operation]=dict(payload=payload,response=copy.deepcopy(response));save(db,state);return response
if __name__=='__main__':
    root=json.load(open(sys.argv[1]));bundle=json.load(open(sys.argv[2]));initialize(sys.argv[3],root);print(json.dumps(verify_and_stage(sys.argv[3],bundle),sort_keys=True))
