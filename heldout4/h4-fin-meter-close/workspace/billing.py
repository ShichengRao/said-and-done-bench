def close_month(events, tiers, start, end):
    totals={}
    for e in events:
        if start <= e['at'] < end and not e['void']:
            a=totals.setdefault(e['account'],{'account':e['account'],'units':0,'amount_cents':0})
            a['units']+=e['units']
            a['amount_cents']+=round(e['units']*tiers[0]['rate_millicents']/1000)
    return sorted(totals.values(),key=lambda x:x['account'])
