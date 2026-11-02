import copy,itertools,json,sys

def _latest(rows,cutoff):
    seen={};selected={}
    for r in rows:
        if r['known']>cutoff:continue
        key=r['id'],r['revision']
        if key in seen and seen[key]!=r:raise ValueError('conflicting visible delivery')
        seen[key]=r
        if r['id'] not in selected or r['revision']>selected[r['id']]['revision']:selected[r['id']]=r
    return list(selected.values())

def _ledger(b,extra):
    cutoff=b['as_of'];end=b['close_day'];terms={}
    for t in _latest(b['terms'],cutoff):
        if not t['signed'] or t['effective']>end:continue
        c=t['contract']
        if c not in terms or t['effective']>terms[c]['effective']:terms[c]=t
    for c,t in terms.items():
        if sum(1 for r in _latest(b['terms'],cutoff) if r['contract']==c and r['signed'] and r['effective']==t['effective'])!=1:raise ValueError('ambiguous terms')
    progress=[r for r in _latest(b['progress']+extra,cutoff) if not r['void'] and r['at']<=end]
    invoices=[r for r in _latest(b['invoices'],cutoff) if not r['void'] and r['at']<=end]
    posted=[r for r in b['posted'] if r['period_end']<=b['open_day']]
    if any(r['contract'] not in terms for r in progress+invoices+posted):raise ValueError('missing contract terms')
    result=[]
    for c,t in sorted(terms.items()):
        keys=sorted(t['obligations']);weights=sum(t['obligations'][k]['weight'] for k in keys)
        allocation={k:t['price_cents']*t['obligations'][k]['weight']//weights for k in keys}
        remaining=t['price_cents']-sum(allocation.values())
        order=sorted(keys,key=lambda k:(-(t['price_cents']*t['obligations'][k]['weight']%weights),k))
        for k in order[:remaining]:allocation[k]+=1
        oldkeys={r['obligation'] for r in posted if r['contract']==c}
        # A retired obligation may have an opening balance, but current progress must reference current terms.
        if any(r['obligation'] not in keys for r in progress if r['contract']==c):raise ValueError('unknown current obligation')
        lines=[]
        for k in sorted(set(keys)|oldkeys):
            events=[r for r in progress if r['contract']==c and r['obligation']==k]
            count=sum(r['units'] for r in events)
            if count<0:raise ValueError('negative delivered units')
            count=min(count,t['obligations'][k]['units']) if k in keys else 0
            value=allocation.get(k,0)
            recognized=(2*value*count+t['obligations'][k]['units'])//(2*t['obligations'][k]['units']) if k in keys else 0
            history=[r for r in posted if r['contract']==c and r['obligation']==k];opening=sum(r['cents'] for r in history)
            lines.append({'id':k,'allocated_cents':value,'completed_units':count,'recognized_cents':recognized,'opening_cents':opening,'period_cents':recognized-opening,'progress_sources':sorted(r['id'] for r in events),'opening_sources':sorted(r['id'] for r in history)})
        billed=sum(r['cents'] for r in invoices if r['contract']==c);recognized=sum(l['recognized_cents'] for l in lines)
        result.append({'id':c,'terms':{'id':t['id'],'revision':t['revision']},'price_cents':t['price_cents'],'billed_cents':billed,'recognized_cents':recognized,'deferred_cents':billed-recognized,'period_cents':sum(l['period_cents'] for l in lines),'invoice_sources':sorted(r['id'] for r in invoices if r['contract']==c),'obligations':lines})
    return result

def rollforward(bundle):
    contracts=_ledger(bundle,[]);amount=sum(c['period_cents'] for c in contracts);review=None
    for n in range(len(bundle['proposals'])+1):
        for chosen in itertools.combinations(bundle['proposals'],n):
            extra=[r for p in chosen for r in p['progress']]
            try:ledger=_ledger(bundle,extra)
            except ValueError:continue
            total=sum(c['period_cents'] for c in ledger)
            if total!=bundle['requested_cents']:continue
            ids=sorted(p['id'] for p in chosen);cost=sum(p['cost'] for p in chosen);key=(cost,len(ids),ids)
            if review is None or key<review[0]:review=(key,{'cost':cost,'proposals':ids,'period_cents':total})
    return {'contracts':contracts,'requested_cents':bundle['requested_cents'],'period_cents':amount,'variance_cents':amount-bundle['requested_cents'],'complete':amount==bundle['requested_cents'],'owner_review':review[1] if review else None}

if __name__=='__main__':print(json.dumps(rollforward(json.load(open(sys.argv[1]))),sort_keys=True))
