"""Immutable differential invoice postings over corrected source deliveries."""
import copy,json,sqlite3

def _initial():return {'clock':0,'periods':{},'targets':{},'history':[],'operations':{}}

def initialize(path):
    with sqlite3.connect(path,timeout=15) as db:
        db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, body TEXT NOT NULL)')
        db.execute('INSERT OR IGNORE INTO state VALUES (1,?)',(json.dumps(_initial()),))

def _visible(rows,as_of):
    seen={};latest={}
    for row in rows:
        if row['known']>as_of:continue
        key=(row['id'],row['revision'])
        if key in seen and seen[key]!=row:raise ValueError('conflicting delivery')
        seen[key]=row
        if row['id'] not in latest or row['revision']>latest[row['id']]['revision']:latest[row['id']]=row
    return list(latest.values())

def _price(units,tiers):
    last=0;amount=0
    for tier in tiers:
        n=units if tier['up_to'] is None else min(units,tier['up_to']-last)
        amount+=n*tier['millicents'];units-=n
        if tier['up_to'] is not None:last=tier['up_to']
        if not units:break
    return amount

def _targets(command):
    usage=_visible(command['usage'],command['as_of'])
    rates=_visible(command['tariffs'],command['as_of'])
    groups={}
    for row in usage:
        if row['void'] or not command['start']<=row['at']<command['end']:continue
        candidates=[r for r in rates if r['meter']==row['meter'] and r['from']<=row['at']<r['until']]
        if len(candidates)!=1:raise ValueError('selected usage needs exactly one tariff')
        r=candidates[0];key=(row['account'],row['meter'],r['id'])
        if key not in groups:groups[key]=[0,r['tiers']]
        groups[key][0]+=row['units']
    raw={k:_price(n,t) for k,(n,t) in groups.items()}
    target={k:{'units':groups[k][0],'amount_cents':raw[k]//1000} for k in groups}
    for account in sorted({k[0] for k in groups}):
        keys=[k for k in groups if k[0]==account]
        rounded=(sum(raw[k] for k in keys)+500)//1000
        residual=rounded-sum(target[k]['amount_cents'] for k in keys)
        order=sorted(keys,key=lambda k:(-(raw[k]%1000),k[1],k[2]))
        for key in order[:residual]:target[key]['amount_cents']+=1
    return {':'.join(k):v for k,v in target.items()}

def _invoices(target):
    accounts={}
    for key,value in sorted(target.items(),key=lambda kv:tuple(kv[0].split(':'))):
        a,m,t=key.split(':');accounts.setdefault(a,[]).append({'meter':m,'tariff':t,**value})
    return [{'account':a,'amount_cents':sum(v['amount_cents'] for v in lines),'lines':lines} for a,lines in sorted(accounts.items())]

def close(path,command):
    with sqlite3.connect(path,timeout=15) as db:
        db.execute('BEGIN IMMEDIATE')
        state=json.loads(db.execute('SELECT body FROM state WHERE id=1').fetchone()[0])
        op=command['operation_id']
        if op in state['operations']:
            previous=state['operations'][op]
            if previous['command']!=command:raise ValueError('operation conflict')
            return copy.deepcopy(previous['response'])
        if command['as_of']<state['clock']:raise ValueError('clock moved backwards')
        period=command['period'];bounds=[command['start'],command['end']]
        if period in state['periods'] and state['periods'][period]!=bounds:raise ValueError('period bounds changed')
        if any(p!=period and max(bounds[0],b[0])<min(bounds[1],b[1]) for p,b in state['periods'].items()):raise ValueError('overlapping periods')
        current=_targets(command);old=state['targets'].get(period,{})
        for k in old:current.setdefault(k,{'units':0,'amount_cents':0})
        postings=[]
        for key,v in sorted(current.items(),key=lambda kv:tuple(kv[0].split(':'))):
            prior=old.get(key,{'units':0,'amount_cents':0});u=v['units']-prior['units'];c=v['amount_cents']-prior['amount_cents']
            if u or c:
                a,m,t=key.split(':');postings.append({'account':a,'meter':m,'tariff':t,'units_delta':u,'cents_delta':c})
        response={'operation_id':op,'period':period,'as_of':command['as_of'],'invoices':_invoices(current),'postings':postings}
        state['periods'][period]=bounds;state['targets'][period]=current;state['clock']=command['as_of']
        state['history']=[response];state['operations'][op]={'command':copy.deepcopy(command),'response':response}
        db.execute('UPDATE state SET body=? WHERE id=1',(json.dumps(state),))
        return copy.deepcopy(response)

def snapshot(path):
    with sqlite3.connect(path,timeout=15) as db:
        s=json.loads(db.execute('SELECT body FROM state WHERE id=1').fetchone()[0])
    return {'clock':s['clock'],'periods':s['periods'],'invoices':{p:_invoices(t) for p,t in sorted(s['targets'].items())},'history':s['history']}
