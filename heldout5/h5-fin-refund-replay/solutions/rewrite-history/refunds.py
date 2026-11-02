import copy,json,sqlite3

def initialize(path,captures):
    seed=sorted(copy.deepcopy(captures),key=lambda c:c['id'])
    with sqlite3.connect(path,timeout=20) as db:
        db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT body FROM state WHERE id=1').fetchone()
        if old:
            if json.loads(old[0])['seed']!=seed:raise ValueError('different capture seed')
        else:db.execute('INSERT INTO state VALUES(1,?)',(json.dumps({'seed':seed,'clock':0,'refunds':{},'settlements':{},'history':[],'operations':{}}),))

def _balances(s):
    totals={c['id']:{'refunded_cents':0,'held_cents':0} for c in s['seed']}
    for event in s['settlements'].values():
        for a in event['allocations']:totals[a['capture']]['refunded_cents']+=a['cents']-a['reversed_cents']
    for r in s['refunds'].values():
        for a in r['allocations']:totals[a['capture']]['held_cents']+=a['cents']
    return totals

def apply(path,command):
    db=sqlite3.connect(path,timeout=20)
    try:
        db.execute('BEGIN IMMEDIATE');s=json.loads(db.execute('SELECT body FROM state WHERE id=1').fetchone()[0]);op=command['operation_id']
        if op in s['operations']:
            old=s['operations'][op]
            if old['command']!=command:raise ValueError('operation conflict')
            db.rollback();return copy.deepcopy(old['response'])
        now=command['at']
        if now<s['clock']:raise ValueError('time moved backwards')
        for r in s['refunds'].values():
            if r['status']=='held' and r['expires']<=now:
                r['status']='expired';r['version']+=1
                for a in r['allocations']:a['cents']=0
        kind=command['kind'];r=None
        if kind=='reserve':
            rid=command['refund']
            if rid in s['refunds'] or command['until']<=now:raise ValueError('invalid reservation')
            captures={c['id']:c for c in s['seed']}
            if any(cid not in captures for cid in command['candidates']):raise ValueError('unknown capture')
            balances=_balances(s);left=command['cents'];alloc=[];expires=command['until']
            for cid in command['candidates']:
                c=captures[cid]
                if c['merchant']!=command['merchant'] or c['currency']!=command['currency'] or c['refund_until']<=now:continue
                available=c['captured_cents']-balances[cid]['refunded_cents']-balances[cid]['held_cents'];take=min(left,available)
                if take:alloc.append({'capture':cid,'cents':take});left-=take;expires=min(expires,c['refund_until'])
                if left==0:break
            if left:result='unavailable'
            else:
                r={'id':rid,'merchant':command['merchant'],'currency':command['currency'],'requested_cents':command['cents'],'expires':expires,'version':1,'status':'held','settled_cents':0,'reversed_cents':0,'allocations':alloc};s['refunds'][rid]=r;result='reserved'
        else:
            if kind=='reverse':
                if command['settlement'] not in s['settlements']:raise ValueError('unknown settlement')
                event=s['settlements'][command['settlement']];rid=event['refund']
            else:rid=command['refund']
            if rid not in s['refunds']:raise ValueError('unknown refund')
            r=s['refunds'][rid]
            if r['version']!=command['expected_version']:raise ValueError('stale version')
            if kind in ('settle','release') and r['status']!='held':raise ValueError('refund has no live hold')
            if kind=='settle':
                left=command['cents']
                if left>sum(a['cents'] for a in r['allocations']):raise ValueError('settlement exceeds hold')
                allocations=[]
                for a in r['allocations']:
                    take=min(left,a['cents']);a['cents']-=take;left-=take
                    if take:allocations.append({'capture':a['capture'],'cents':take,'reversed_cents':0})
                s['settlements'][op]={'id':op,'refund':rid,'allocations':allocations};r['settled_cents']+=command['cents']
                if not any(a['cents'] for a in r['allocations']):r['status']='settled'
                result='settled'
            elif kind=='reverse':
                left=command['cents']
                if left>sum(a['cents']-a['reversed_cents'] for a in event['allocations']):raise ValueError('reversal exceeds settlement')
                for a in event['allocations']:
                    take=min(left,a['cents']-a['reversed_cents']);a['reversed_cents']+=take;left-=take
                r['reversed_cents']+=command['cents'];result='reversed'
            elif kind=='release':
                for a in r['allocations']:a['cents']=0
                r['status']='released';result='released'
            else:raise ValueError('unknown operation kind')
            r['version']+=1
        s['clock']=now;response={'operation_id':op,'result':result,'refund':copy.deepcopy(r)};s['history']=[response];s['operations'][op]={'command':copy.deepcopy(command),'response':response}
        db.execute('UPDATE state SET body=? WHERE id=1',(json.dumps(s),));db.commit();return copy.deepcopy(response)
    except Exception:db.rollback();raise
    finally:db.close()

def snapshot(path):
    with sqlite3.connect(path,timeout=20) as db:s=json.loads(db.execute('SELECT body FROM state WHERE id=1').fetchone()[0])
    balance=_balances(s);captures=[]
    for c in s['seed']:
        b=balance[c['id']];captures.append(dict(c,**b,available_cents=c['captured_cents']-b['refunded_cents']-b['held_cents']))
    return {'clock':s['clock'],'captures':captures,'refunds':[s['refunds'][k] for k in sorted(s['refunds'])],'settlements':[s['settlements'][k] for k in sorted(s['settlements'])],'history':s['history']}
