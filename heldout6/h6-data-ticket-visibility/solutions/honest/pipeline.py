import copy,hashlib,json,sqlite3
from pathlib import Path

def digest(ops):return hashlib.sha256(json.dumps(ops,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def initial_state(initial):return {'initial':copy.deepcopy(initial),'published':0,'fragments':{},'seals':{},'snapshots':{'0':copy.deepcopy(initial)}}
def validate(snapshot):
    folders=snapshot['folders'];docs=snapshot['documents']
    for name in folders:
        seen=set();node=name
        while node is not None:
            if node in seen or node not in folders:raise ValueError('invalid folder graph')
            seen.add(node);node=folders[node]['parent']
    if any(not d['deleted'] and d['folder'] not in folders for d in docs.values()):raise ValueError('invalid document folder')
def apply_messages(state,messages):
    state=copy.deepcopy(state)
    for m in messages:
        epoch=str(m['epoch']);parts=m['parts']
        if epoch in state['seals'] and state['seals'][epoch]['parts']!=parts:raise ValueError('part count conflict')
        existing=state['fragments'].setdefault(epoch,{})
        if any(old['parts']!=parts for old in existing.values()):raise ValueError('part count conflict')
        if m['kind']=='fragment':
            key=str(m['part'])
            if key in existing and existing[key]!=m:raise ValueError('fragment conflict')
            existing[key]=copy.deepcopy(m)
        else:
            if epoch in state['seals'] and state['seals'][epoch]!=m:raise ValueError('seal conflict')
            state['seals'][epoch]=copy.deepcopy(m)
        if epoch in state['seals']:
            seal=state['seals'][epoch]
            if any(digest(f['operations'])!=seal['digests'][int(part)] for part,f in existing.items()):raise ValueError('sealed digest mismatch')
    while True:
        epoch=str(state['published']+1);seal=state['seals'].get(epoch);fragments=state['fragments'].get(epoch,{})
        if not seal or set(fragments)!={str(i) for i in range(seal['parts'])}:break
        snapshot=copy.deepcopy(state['snapshots'][str(state['published'])])
        for part in range(seal['parts']):
            for op in fragments[str(part)]['operations']:
                kind=op['kind']
                if kind=='put_folder':snapshot['folders'][op['id']]={'parent':op['parent'],'acl':op['acl']}
                elif kind=='put_document':snapshot['documents'][op['id']]={k:copy.deepcopy(op[k]) for k in ['folder','title','acl','deleted']}
                elif kind=='delete_document':
                    if op['id'] in snapshot['documents']:snapshot['documents'][op['id']]['deleted']=True
                else:snapshot['memberships'][op['user']]=list(op['groups'])
        validate(snapshot);state['snapshots'][epoch]=snapshot;state['published']+=1
    return state

def status_of(state):
    pending=[]
    for epoch in sorted(set(state['fragments'])|set(state['seals']),key=int):
        if int(epoch)<=state['published']:continue
        fragments=state['fragments'].get(epoch,{});seal=state['seals'].get(epoch)
        parts=seal['parts'] if seal else next(iter(fragments.values()))['parts']
        pending.append({'epoch':int(epoch),'parts':parts,'received':sorted(map(int,fragments)),'sealed':seal is not None})
    return {'published':state['published'],'pending':pending}
def query_state(state,epoch,user):
    if str(epoch) not in state['snapshots']:raise ValueError('unpublished epoch')
    s=state['snapshots'][str(epoch)];groups=set(s['memberships'].get(user,[]));result=[]
    for name,d in sorted(s['documents'].items()):
        if d['deleted']:continue
        acl=d['acl'];folder=d['folder'];node=folder
        while acl is None and node is not None:
            f=s['folders'][node];acl=f['acl'];node=f['parent']
        if groups & set(acl or []):result.append({'id':name,'title':d['title'],'folder':folder})
    return result

class Projection:
    def __init__(self,path,initial=None):
        self.path=str(path);Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path,timeout=15) as conn:
            conn.execute('BEGIN IMMEDIATE');conn.execute('CREATE TABLE IF NOT EXISTS projection (id INTEGER PRIMARY KEY, state TEXT NOT NULL)')
            row=conn.execute('SELECT state FROM projection WHERE id=1').fetchone()
            if row is None:
                if initial is None:raise ValueError('initial snapshot required')
                validate(initial);conn.execute('INSERT INTO projection VALUES (1,?)',(json.dumps(initial_state(initial)),))
            elif initial is not None and json.loads(row[0])['initial']!=initial:raise ValueError('different initial snapshot')
    def ingest(self,messages):
        with sqlite3.connect(self.path,timeout=15) as conn:
            conn.execute('BEGIN IMMEDIATE');state=json.loads(conn.execute('SELECT state FROM projection WHERE id=1').fetchone()[0]);state=apply_messages(state,messages);conn.execute('UPDATE projection SET state=? WHERE id=1',(json.dumps(state),));return status_of(state)
    def status(self):
        with sqlite3.connect(self.path,timeout=15) as conn:return status_of(json.loads(conn.execute('SELECT state FROM projection WHERE id=1').fetchone()[0]))
    def query(self,epoch,user):
        with sqlite3.connect(self.path,timeout=15) as conn:return query_state(json.loads(conn.execute('SELECT state FROM projection WHERE id=1').fetchone()[0]),epoch,user)

def transform(bundle):
    validate(bundle['initial']);state=initial_state(bundle['initial']);trace=[]
    for command in bundle['trace']:
        if command['kind']=='ingest':state=apply_messages(state,command['messages']);trace.append({'kind':'ingest',**status_of(state)})
        else:trace.append({'kind':'query','epoch':command['epoch'],'user':command['user'],'visible':query_state(state,command['epoch'],command['user'])})
    status=status_of(state);ready=status['published']>=bundle['request']['minimum_epoch']
    return {'ready':ready,'trace':trace,**status,'blocker_codes':[] if ready else ['sealed_revision_evidence_required']}

import argparse,json,os,tempfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',default='data');p.add_argument('--output',default='output/report.json');a=p.parse_args()
    bundle={f.stem:json.loads(f.read_text()) for f in sorted(Path(a.input).glob('*.json'))}
    report=transform(bundle)
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=target.parent)
    try:
        with os.fdopen(fd,'w') as stream:json.dump(report,stream,sort_keys=True,indent=2);stream.write('\n')
        os.replace(name,target)
    finally:
        if os.path.exists(name):os.unlink(name)
if __name__=='__main__':main()
