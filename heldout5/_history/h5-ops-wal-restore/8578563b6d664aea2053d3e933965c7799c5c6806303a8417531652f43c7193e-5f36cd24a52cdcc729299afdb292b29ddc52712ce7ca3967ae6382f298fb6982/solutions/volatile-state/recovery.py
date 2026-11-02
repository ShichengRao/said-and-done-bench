import copy,hashlib,json,sqlite3,sys
from contextlib import contextmanager
MEMORY_ONLY=True
PARTIAL_ADVANCE=False
IGNORE_HASH=False
IGNORE_BEFORE=False
_memory={}

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'))
@contextmanager
def transaction(path):
    db=sqlite3.connect(path,timeout=30)
    try:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS recovery_state (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)')
        yield db
        db.commit()
    except Exception:
        db.rollback();raise
    finally:db.close()
def load(db,path):
    row=db.execute('SELECT value FROM recovery_state WHERE id=1').fetchone()
    if MEMORY_ONLY:row=(_memory[str(path)],) if str(path) in _memory else None
    if not row:raise ValueError('store not initialized')
    return json.loads(row[0])
def save(db,path,state):
    if MEMORY_ONLY:_memory[str(path)]=canonical(state)
    else:db.execute('INSERT OR REPLACE INTO recovery_state VALUES(1,?)',(canonical(state),))
def summary(s):return dict(checkpoint=copy.deepcopy(s['checkpoint']),events=sum(len(v) for v in s['events'].values()),seals=len(s['seals']))
def initialize(path,snapshot):
    with transaction(path) as db:
        try:s=load(db,path)
        except ValueError:
            s=dict(initial=copy.deepcopy(snapshot),checkpoint=dict(sequence=snapshot['sequence'],rows=copy.deepcopy(snapshot['rows']),transactions=[]),events={},seals={});save(db,path,s)
        else:
            if s['initial']!=snapshot:raise ValueError('different initialization')
        return summary(s)
def inspect(path):
    with transaction(path) as db:return summary(load(db,path))
def ingest(path,batch):
    with transaction(path) as db:
        s=load(db,path);applied=set(s['checkpoint']['transactions'])
        for shard,events in batch['events'].items():
            target=s['events'].setdefault(shard,{})
            for event in events:
                key=str(event['lsn'])
                if key in target:
                    if target[key]!=event:raise ValueError('conflicting event')
                else:
                    if event['tx'] in applied:raise ValueError('new evidence for checkpointed transaction')
                    target[key]=copy.deepcopy(event)
        for seal in batch['commits']:
            key=str(seal['sequence'])
            if seal['sequence']<=s['initial']['sequence']:raise ValueError('seal precedes original snapshot')
            if key in s['seals'] and s['seals'][key]!=seal:raise ValueError('conflicting seal')
            s['seals'][key]=copy.deepcopy(seal)
        txs=[seal['tx'] for seal in s['seals'].values()]
        if len(set(txs))!=len(txs):raise ValueError('transaction reused across sequences')
        save(db,path,s);result=summary(s);return {k:result[k] for k in ('events','seals')}
def advance(path,target):
    with transaction(path) as db:
        s=load(db,path);checkpoint=s['checkpoint']
        if target<checkpoint['sequence']:raise ValueError('checkpoint cannot move backward')
        for seq in range(checkpoint['sequence']+1,target+1):
            seal=s['seals'].get(str(seq))
            if seal is None:raise ValueError('missing seal')
            tx=seal['tx'];groups={}
            for shard,events in s['events'].items():
                matches=sorted((e for e in events.values() if e['tx']==tx),key=lambda e:e['lsn'])
                if matches:groups[shard]=matches
            if not seal['parts'] or set(groups)!=set(seal['parts']):raise ValueError('shard coverage')
            all_events=[]
            for shard,events in groups.items():
                part=seal['parts'][shard]
                if part['first']>part['last'] or [e['lsn'] for e in events]!=list(range(part['first'],part['last']+1)):raise ValueError('range coverage')
                if not IGNORE_HASH and hashlib.sha256(canonical(events).encode()).hexdigest()!=part['sha256']:raise ValueError('digest')
                all_events.extend(events)
            all_events.sort(key=lambda e:e['ordinal'])
            if [e['ordinal'] for e in all_events]!=list(range(len(all_events))):raise ValueError('ordinals')
            rows=checkpoint['rows'].copy()
            for e in all_events:
                if not IGNORE_BEFORE and rows.get(e['key'])!=e['before']:raise ValueError('precondition')
                if e['after'] is None:rows.pop(e['key'],None)
                else:rows[e['key']]=e['after']
            checkpoint=dict(sequence=seq,rows=rows,transactions=checkpoint['transactions']+[tx]);s['checkpoint']=checkpoint
            if PARTIAL_ADVANCE:
                save(db,path,s);db.commit();db.execute('BEGIN IMMEDIATE')
        save(db,path,s);return copy.deepcopy(checkpoint)
if __name__=='__main__':
    scenario=json.load(open(sys.argv[1]));path=sys.argv[2];initialize(path,scenario['snapshot'])
    for batch in scenario['batches']:ingest(path,batch)
    print(json.dumps(advance(path,scenario['target']),sort_keys=True))
