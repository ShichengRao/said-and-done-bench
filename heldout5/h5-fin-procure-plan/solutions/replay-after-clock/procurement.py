import copy,json,sqlite3

def initialize(path,stock,transfers):
    seed={'stock':sorted(copy.deepcopy(stock),key=lambda x:(x['warehouse'],x['sku'])),'transfers':sorted(copy.deepcopy(transfers),key=lambda x:x['id'])}
    with sqlite3.connect(path,timeout=20) as db:
        db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)');db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT body FROM state WHERE id=1').fetchone()
        if row:
            if json.loads(row[0])['seed']!=seed:raise ValueError('different seed')
        else:
            state={'seed':seed,'clock':0,'stock':{r['warehouse']+':'+r['sku']:r['quantity'] for r in stock},'baskets':{},'transfers':{t['id']:{'id':t['id'],'observed':[],'status':'waiting'} for t in transfers},'operations':{},'history':[]}
            db.execute('INSERT INTO state VALUES(1,?)',(json.dumps(state),))

def _held(s,ignore=None):
    h={k:0 for k in s['stock']}
    for bid,b in s['baskets'].items():
        if b['status']=='held' and bid!=ignore:
            for a in b['allocations']:h[a['warehouse']+':'+a['sku']]+=a['quantity']
    return h

def _allocate(s,request,ignore=None):
    held=_held(s,ignore);alloc=[]
    if any(w+':'+sku not in s['stock'] for sku in request['needs'] for w in request['routes'][sku]):raise ValueError('unknown stock route')
    for sku,qty in sorted(request['needs'].items()):
        left=qty
        for warehouse in request['routes'][sku]:
            key=warehouse+':'+sku
            if key not in s['stock']:raise ValueError('unknown stock route')
            take=min(left,s['stock'][key]-held[key])
            if take:alloc.append({'sku':sku,'warehouse':warehouse,'quantity':take});left-=take
        if left:return None
    return alloc

def apply(path,command):
    db=sqlite3.connect(path,timeout=20)
    try:
        db.execute('BEGIN IMMEDIATE');s=json.loads(db.execute('SELECT body FROM state WHERE id=1').fetchone()[0]);op=command['operation_id']
        if command['at']<s['clock']:raise ValueError('old time')
        if op in s['operations']:
            old=s['operations'][op]
            if old['command']!=command:raise ValueError('operation conflict')
            db.rollback();return copy.deepcopy(old['response'])
        now=command['at']
        if now<s['clock']:raise ValueError('time moved backwards')
        for b in s['baskets'].values():
            if b['status']=='held' and b['expires']<=now:b['status']='expired';b['version']+=1
        kind=command['kind'];basket=None;transfer=None
        if kind=='receive':
            tid=command['transfer']
            if tid not in s['transfers']:raise ValueError('unknown transfer')
            transfer=s['transfers'][tid];event=command['event'];manifest=next(t for t in s['seed']['transfers'] if t['id']==tid)
            if event not in transfer['observed']:transfer['observed'].append(event);transfer['observed'].sort()
            if 'depart' in transfer['observed'] and transfer['status']=='waiting':
                held=_held(s)
                if any(s['stock'][manifest['source']+':'+sku]-held[manifest['source']+':'+sku]<qty for sku,qty in manifest['lines'].items()):raise ValueError('transfer stock unavailable')
                for sku,qty in manifest['lines'].items():s['stock'][manifest['source']+':'+sku]-=qty
                transfer['status']='in_transit'
            if 'arrive' in transfer['observed'] and transfer['status']=='in_transit':
                for sku,qty in manifest['lines'].items():s['stock'][manifest['destination']+':'+sku]+=qty
                transfer['status']='arrived'
            result='received'
        elif kind in ('reserve','amend'):
            bid=command['basket']
            if command['until']<=now:raise ValueError('invalid expiry')
            if kind=='reserve':
                if bid in s['baskets']:raise ValueError('basket exists')
            else:
                if bid not in s['baskets']:raise ValueError('unknown basket')
                basket=s['baskets'][bid]
                if basket['status']!='held' or basket['version']!=command['expected_version']:raise ValueError('stale or terminal basket')
            alloc=_allocate(s,command['request'],bid if kind=='amend' else None)
            if alloc is None:result='unavailable'
            else:
                basket={'id':bid,'version':1 if kind=='reserve' else basket['version']+1,'status':'held','expires':command['until'],'request':copy.deepcopy(command['request']),'allocations':alloc};s['baskets'][bid]=basket;result='reserved' if kind=='reserve' else 'amended'
        elif kind in ('commit','release'):
            bid=command['basket']
            if bid not in s['baskets']:raise ValueError('unknown basket')
            basket=s['baskets'][bid]
            if basket['status']!='held' or basket['version']!=command['expected_version']:raise ValueError('stale or terminal basket')
            if kind=='commit':
                for a in basket['allocations']:s['stock'][a['warehouse']+':'+a['sku']]-=a['quantity']
            basket['status']='committed' if kind=='commit' else 'released';basket['version']+=1;result=basket['status']
        else:raise ValueError('unknown kind')
        s['clock']=now;response={'operation_id':op,'result':result,'basket':copy.deepcopy(basket),'transfer':copy.deepcopy(transfer)};s['history'].append(response);s['operations'][op]={'command':copy.deepcopy(command),'response':response}
        db.execute('UPDATE state SET body=? WHERE id=1',(json.dumps(s),));db.commit();return copy.deepcopy(response)
    except Exception:db.rollback();raise
    finally:db.close()

def snapshot(path):
    with sqlite3.connect(path,timeout=20) as db:s=json.loads(db.execute('SELECT body FROM state WHERE id=1').fetchone()[0])
    h=_held(s);stock=[]
    for key,qty in sorted(s['stock'].items(),key=lambda kv:tuple(kv[0].split(':'))):
        warehouse,sku=key.split(':');stock.append({'warehouse':warehouse,'sku':sku,'on_hand':qty,'held':h[key],'available':qty-h[key]})
    return {'clock':s['clock'],'stock':stock,'baskets':[s['baskets'][k] for k in sorted(s['baskets'])],'transfers':[s['transfers'][k] for k in sorted(s['transfers'])],'history':s['history']}
