"""Durable source reconstruction and pooled, conserved billing adjustments."""
import copy,json,sqlite3

def _seed(config):
    return {k:sorted(copy.deepcopy(config[k]),key=lambda x:x['id']) for k in ('periods','meters','pools')}

def initialize(path,config):
    seed=_seed(config)
    with sqlite3.connect(path,timeout=20) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, body TEXT NOT NULL)')
        old=db.execute('SELECT body FROM state WHERE id=1').fetchone()
        if old:
            if json.loads(old[0])['config']!=seed:raise ValueError('changed seed')
        else:
            db.execute('INSERT INTO state VALUES (1,?)',(json.dumps(dict(config=seed,clock=0,deliveries=[],targets={},history=[],operations={})),))

def _visible(rows,as_of):
    seen={};latest={}
    for r in rows:
        if r['known']>as_of:continue
        key=r['id'],r['revision']
        if key in seen and seen[key]!=r:raise ValueError('conflicting visible delivery')
        seen[key]=r
        if r['id'] not in latest or r['revision']>latest[r['id']]['revision']:latest[r['id']]=r
    return [r for r in latest.values() if not r['void']]

def _price(n,tiers):
    amount=0;previous=0
    for tier in tiers:
        take=n if tier['up_to'] is None else min(n,tier['up_to']-previous)
        amount+=take*tier['millicents'];n-=take
        if tier['up_to'] is not None:previous=tier['up_to']
        if n==0:break
    return amount

def _targets(config,rows,as_of):
    meters={m['id']:m for m in config['meters']};periods={p['id']:p for p in config['periods']};pools={p['id']:p for p in config['pools']}
    groups={};intervals={};units={}
    for r in _visible(rows,as_of):groups.setdefault((r['meter'],r['epoch']),[]).append(r)
    for (meter,epoch),readings in groups.items():
        readings.sort(key=lambda r:r['at'])
        if len({r['at'] for r in readings})!=len(readings):raise ValueError('duplicate timestamp')
        for left,right in zip(readings,readings[1:]):
            start,end=left['at'],right['at'];amount=right['counter']-left['counter']
            if amount<0:raise ValueError('counter decreased')
            intervals.setdefault(meter,[]).append((start,end))
            overlaps={p['id']:max(0,min(end,p['end'])-max(start,p['start'])) for p in config['periods']}
            overlaps={k:v for k,v in overlaps.items() if v}
            if sum(overlaps.values())!=end-start:raise ValueError('uncovered interval')
            split={k:amount*v//(end-start) for k,v in overlaps.items()}
            for key in sorted(overlaps,key=lambda k:(-(amount*overlaps[k]%(end-start)),k))[:amount-sum(split.values())]:split[key]+=1
            for period,n in split.items():
                key=(period,meters[meter]['account'],meter);units[key]=units.get(key,0)+n
    for spans in intervals.values():
        spans.sort()
        if any(a[1]>b[0] for a,b in zip(spans,spans[1:])):raise ValueError('overlapping epochs')
    pricing={}
    for key in units:
        period,account,meter=key;pricing.setdefault((periods[period]['cycle'],meters[meter]['pool']),[]).append(key)
    target={k:{'units':v,'cents':0} for k,v in units.items()}
    for (cycle,pool),keys in pricing.items():
        total=sum(units[k] for k in keys);raw=_price(total,pools[pool]['tiers'])
        if not total:continue
        denom=total*1000
        for key in keys:target[key]['cents']=raw*units[key]//denom
        residual=(raw+500)//1000-sum(target[k]['cents'] for k in keys)
        for key in sorted(keys,key=lambda k:(-(raw*units[k]%denom),k))[:residual]:target[key]['cents']+=1
    return {':'.join(k):v for k,v in target.items()}

def _list(target):
    return [dict(zip(('period','account','meter'),k.split(':')),**v) for k,v in sorted(target.items(),key=lambda kv:tuple(kv[0].split(':')))]

def close(path,command):
    with sqlite3.connect(path,timeout=20) as db:
        db.execute('BEGIN IMMEDIATE')
        s=json.loads(db.execute('SELECT body FROM state WHERE id=1').fetchone()[0]);op=command['operation_id']
        if op in s['operations']:
            saved=s['operations'][op]
            if saved['command']!=command:raise ValueError('operation conflict')
            return copy.deepcopy(saved['response'])
        if command['as_of']<s['clock']:raise ValueError('clock regression')
        deliveries={json.dumps(r,sort_keys=True,separators=(',',':')):r for r in command['readings']}
        s['deliveries']=list(deliveries.values())
        target=_targets(s['config'],s['deliveries'],command['as_of']);old=s['targets']
        for key in old:target.setdefault(key,dict(units=0,cents=0))
        postings=[]
        for key,new in sorted(target.items(),key=lambda kv:tuple(kv[0].split(':'))):
            prior=old.get(key,dict(units=0,cents=0));u=new['units']-prior['units'];c=new['cents']-prior['cents']
            if u or c:postings.append(dict(zip(('period','account','meter'),key.split(':')),units_delta=u,cents_delta=c))
        response=dict(operation_id=op,as_of=command['as_of'],targets=_list(target),postings=postings)
        s['targets']=target;s['clock']=command['as_of'];s['history'].append(response)
        s['operations'][op]=dict(command=copy.deepcopy(command),response=response)
        db.execute('UPDATE state SET body=? WHERE id=1',(json.dumps(s),))
        return copy.deepcopy(response)

def snapshot(path):
    with sqlite3.connect(path,timeout=20) as db:s=json.loads(db.execute('SELECT body FROM state WHERE id=1').fetchone()[0])
    return dict(clock=s['clock'],config=s['config'],delivery_count=len(s['deliveries']),targets=_list(s['targets']),history=s['history'])
