from datetime import datetime

def instant(value):
    if not isinstance(value,str): raise ValueError('timestamp')
    try: t=datetime.fromisoformat(value.replace('Z','+00:00'))
    except (ValueError,TypeError): raise ValueError('timestamp')
    if t.utcoffset() is None: raise ValueError('timezone')
    return t

def integer(v,minimum):
    return type(v) is int and v >= minimum

def close_month(events, tiers, start, end):
    try: events=iter(events)
    except TypeError: raise ValueError('events must be iterable')
    start,end=instant(start),instant(end)
    if start >= end: raise ValueError('window')
    if not isinstance(tiers,list) or not tiers: raise ValueError('tiers')
    last=0
    for i,t in enumerate(tiers):
        if not isinstance(t,dict) or set(t) != {'up_to','rate_millicents'}: raise ValueError('tier')
        top=t['up_to']
        if not integer(t['rate_millicents'],0): raise ValueError('rate')
        if top is None:
            if i != len(tiers)-1: raise ValueError('unbounded')
        elif not integer(top,1) or top <= last or i == len(tiers)-1: raise ValueError('boundary')
        if top is not None: last=top
    seen={}; winners={}
    for e in events:
        if not start <= instant(e['at']) < end: continue
        if not isinstance(e,dict) or set(e) != {'event_id','revision','account','at','units','void'}: raise ValueError('event')
        if any(not isinstance(e[k],str) or not e[k] for k in ('event_id','account')): raise ValueError('identity')
        if not integer(e['revision'],1) or not integer(e['units'],0) or type(e['void']) is not bool: raise ValueError('event types')
        instant(e['at'])
        key=(e['event_id'],e['revision'])
        if key in seen and seen[key] != e: raise ValueError('conflicting replay')
        seen[key]=dict(e)
        if e['event_id'] not in winners or winners[e['event_id']]['revision'] < e['revision']:
            winners[e['event_id']]=dict(e)
    totals={}
    for e in winners.values():
        if not e['void'] and start <= instant(e['at']) < end:
            totals[e['account']]=totals.get(e['account'],0)+e['units']
    rows=[]
    for account,units in sorted(totals.items()):
        amount=0; previous=0
        for t in tiers:
            top=units if t['up_to'] is None else t['up_to']
            amount += max(0,min(units,top)-previous)*t['rate_millicents']
            previous=top
        rows.append({'account':account,'units':units,'amount_cents':(amount+500)//1000})
    return rows
