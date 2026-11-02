import copy,json,sqlite3,sys
from contextlib import contextmanager
IGNORE_PAYLOAD=False
TRUST_RECEIPT=True
ADVANCE_ON_DISPATCH=False

def canon(v):return json.dumps(v,sort_keys=True,separators=(',',':'))
@contextmanager
def transaction(path):
    db=sqlite3.connect(path,timeout=30)
    try:
        db.execute('BEGIN IMMEDIATE');db.execute('CREATE TABLE IF NOT EXISTS controller_state(id INTEGER PRIMARY KEY CHECK(id=1),value TEXT NOT NULL)');yield db;db.commit()
    except Exception:db.rollback();raise
    finally:db.close()
def load(db):
    row=db.execute('SELECT value FROM controller_state WHERE id=1').fetchone()
    if row is None:raise ValueError('uninitialized')
    return json.loads(row[0])
def save(db,value):db.execute('INSERT OR REPLACE INTO controller_state VALUES(1,?)',(canon(value),))
def state_ok(config,pods):
    nodes={n['id']:n for n in config['nodes']}
    return set(pods)<=set(nodes) and config['min_ready']<=len(pods)<=config['max_total'] and len({nodes[n]['zone'] for n in pods})>=config['min_zones']
def execute(config,pods,action,revision):
    nodes={n['id']:n for n in config['nodes']};node=action['node'];result=pods.copy()
    if node not in nodes:raise ValueError('unknown node')
    if action['op']=='start':
        if node in result or not nodes[node]['eligible'] or nodes[node]['maintenance']:raise ValueError('illegal start')
        result[node]=revision
    elif action['op']=='stop':
        if node not in result:raise ValueError('illegal stop')
        del result[node]
    else:raise ValueError('unknown action')
    if not state_ok(config,result):raise ValueError('availability')
    return result

def initialize(path,config,initial):
    with transaction(path) as db:
        try:data=load(db)
        except ValueError:
            if not state_ok(config,initial):raise ValueError('invalid initial')
            state=dict(version=0,epoch=0,revision=None,target_nodes=[],nodes=copy.deepcopy(initial),plan=[],step=0,pending=None)
            data=dict(config=copy.deepcopy(config),initial=copy.deepcopy(initial),state=state,attempts={},requests={});save(db,data)
        else:
            if data['config']!=config or data['initial']!=initial:raise ValueError('different initialization')
        return copy.deepcopy(data['state'])
def inspect(path):
    with transaction(path) as db:return copy.deepcopy(load(db)['state'])
def apply(path,request):
    with transaction(path) as db:
        data=load(db);s=data['state'];key=request['id'];payload=canon(request)
        if key in data['requests']:
            previous=data['requests'][key]
            if not IGNORE_PAYLOAD and previous['payload']!=payload:raise ValueError('request ID conflict')
            return copy.deepcopy(previous['response'])
        kind=request['kind'];command=None
        if kind in ('install','tick') and request['expect']!=s['version']:raise ValueError('version mismatch')
        if kind=='install':
            if request['epoch']!=s['epoch']+1:raise ValueError('epoch mismatch')
            cfg=data['config'];nodes={n['id']:n for n in cfg['nodes']};targets=request['target_nodes'];pods=copy.deepcopy(request['observed'])
            if len(set(targets))!=len(targets) or any(n not in nodes or not nodes[n]['eligible'] or nodes[n]['maintenance'] for n in targets) or not state_ok(cfg,pods):raise ValueError('invalid inventory or target')
            for action in request['plan']:pods=execute(cfg,pods,action,request['revision'])
            if set(pods)!=set(targets) or any(v!=request['revision'] for v in pods.values()):raise ValueError('plan does not achieve target')
            s.update(epoch=request['epoch'],revision=request['revision'],target_nodes=copy.deepcopy(targets),nodes=copy.deepcopy(request['observed']),plan=copy.deepcopy(request['plan']),step=0,pending=None);data['attempts']={};status='installed'
        elif kind=='tick':
            if s['pending'] is not None:status='waiting';command=copy.deepcopy(s['pending'])
            elif s['step']==len(s['plan']):status='done'
            else:
                step=s['step'];attempt=data['attempts'].get(str(step),0)+1;data['attempts'][str(step)]=attempt;action=s['plan'][step]
                command=dict(id=f"{s['epoch']}:{step}:{attempt}",epoch=s['epoch'],step=step,attempt=attempt,op=action['op'],node=action['node'],revision=s['revision'] if action['op']=='start' else None);s['pending']=copy.deepcopy(command);status='command'
                if ADVANCE_ON_DISPATCH:s['nodes']=execute(data['config'],s['nodes'],command,s['revision']);s['step']+=1
        elif kind=='observe':
            pending=s['pending']
            if pending is None or (not TRUST_RECEIPT and (request['epoch']!=pending['epoch'] or request['command']!=pending['id'])):status='stale'
            else:
                s['pending']=None
                if request['success']:
                    s['nodes']=execute(data['config'],s['nodes'],pending,pending['revision']);s['step']+=1;status='applied'
                else:status='retry'
        else:raise ValueError('unknown operation')
        s['version']+=1;response=dict(version=s['version'],epoch=s['epoch'],status=status,step=s['step'],command=command)
        data['requests'][key]=dict(payload=payload,response=copy.deepcopy(response));save(db,data);return response
if __name__=='__main__':
    data=json.load(open(sys.argv[1]));path=sys.argv[2];initialize(path,data['config'],data['initial'])
    for request in data['requests']:apply(path,request)
    print(json.dumps(inspect(path),sort_keys=True))
