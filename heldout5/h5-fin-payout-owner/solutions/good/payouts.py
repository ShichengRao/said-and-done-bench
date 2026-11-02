import copy,itertools,json,sys

def _latest(rows,as_of):
    seen={};winners={}
    for row in rows:
        if row['known']>as_of:continue
        key=(row['id'],row['revision'])
        if key in seen and seen[key]!=row:raise ValueError('conflicting visible delivery')
        seen[key]=row
        if row['id'] not in winners or row['revision']>winners[row['id']]['revision']:winners[row['id']]=row
    return list(winners.values())

def _lots(bundle):
    sources=[r for r in _latest(bundle['settlements'],bundle['as_of']) if not r['void']]
    transfers=[r for r in _latest(bundle['transfers'],bundle['as_of']) if not r['void']]
    totals={};provenance={};attrs={}
    for row in sources:
        key=row['lot'];a=(row['owner'],row['currency'],row['rail'])
        if key in attrs and attrs[key]!=a:raise ValueError('inconsistent lot identity')
        attrs[key]=a;totals[key]=totals.get(key,0)+row['gross']-row['refund']-row['fee'];provenance.setdefault(key,[]).append(row['id'])
    out=[]
    for lot in sorted(totals):
        amount=totals[lot]
        if amount<0:raise ValueError('negative lot')
        if amount==0:continue
        owner,currency,rail=attrs[lot];path=[owner]
        # A transfer at the payout day already applies. At each owner choose its unique latest effective transfer.
        while True:
            options=[r for r in transfers if r['source']==owner and r['effective']<=bundle['payout_day']]
            if not options:break
            day=max(r['effective'] for r in options);w=[r for r in options if r['effective']==day]
            if len(w)!=1:raise ValueError('ambiguous owner transfer')
            owner=w[0]['target']
            if owner in path:raise ValueError('ownership cycle')
            path.append(owner)
        out.append({'id':lot,'owner':owner,'currency':currency,'rail':rail,'cents':amount,'sources':sorted(provenance[lot]),'owner_path':path})
    return out

def _coverage(lots,attestations):
    edges={lot['id']:[a for a in attestations if a['owner']==lot['owner'] and lot['currency'] in a['currencies'] and lot['rail'] in a['rails']] for lot in lots}
    best=None
    for n in range(1,len(lots)+1):
        for chosen in itertools.combinations(lots,n):
            ids=[r['id'] for r in chosen];neighbors={a['id']:a for r in chosen for a in edges[r['id']]}
            required=sum(r['cents'] for r in chosen);capacity=sum(a['cap'] for a in neighbors.values());gap=required-capacity
            if gap<=0:continue
            witness={'lots':ids,'attestations':sorted(neighbors),'required_cents':required,'capacity_cents':capacity,'shortfall_cents':gap}
            key=(-gap,len(ids),ids)
            if best is None or key<best[0]:best=(key,witness)
    requested=sum(r['cents'] for r in lots)
    return requested-(best[1]['shortfall_cents'] if best else 0),best[1] if best else None

def reconcile(bundle):
    lots=_lots(bundle);day=bundle['payout_day']
    attestations=[a for a in _latest(bundle['attestations'],bundle['as_of']) if not a['revoked'] and a['from_day']<=day<a['until_day']]
    funded,cut=_coverage(lots,attestations);total=sum(r['cents'] for r in lots);review=None
    for n in range(len(bundle['proposals'])+1):
        for chosen in itertools.combinations(bundle['proposals'],n):
            amended=copy.deepcopy(attestations)
            for p in chosen:amended.extend(p['attestations'])
            f,_=_coverage(lots,amended)
            if f!=total:continue
            ids=sorted(p['id'] for p in chosen);cost=sum(p['cost'] for p in chosen);key=(cost,len(ids),ids)
            if review is None or key<review[0]:review=(key,{'cost':cost,'proposals':ids})
    return {'lots':lots,'requested_cents':total,'covered_cents':funded,'complete':funded==total,'deficiency':cut,'owner_review':review[1] if review else None}

if __name__=='__main__':print(json.dumps(reconcile(json.load(open(sys.argv[1]))),sort_keys=True))
