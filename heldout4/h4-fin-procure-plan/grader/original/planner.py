def choose(request):
    offers=sorted(request['offers'],key=lambda o:o['id'])
    suppliers=request['suppliers']
    remaining=dict(request['demand'])
    pool_left={name:p['available_units'] for name,p in request['stock_pools'].items()}
    units={name:0 for name in suppliers}
    resources={name:dict(s['capacity']) for name,s in suppliers.items()}
    merchandise={name:0 for name in suppliers}
    best=None

    def visit(index,vector):
        nonlocal best
        if index==len(offers):
            if any(remaining.values()):return
            if any(n and not suppliers[s]['min_units']<=n<=suppliers[s]['max_units'] for s,n in units.items()):return
            price=0
            for name,n in units.items():
                if not n:continue
                supplier=suppliers[name]
                threshold=max((d for d in supplier['discounts'] if d['minimum_units']<=n),key=lambda d:d['minimum_units'])
                bps=threshold['discount_bps']
                discount=(merchandise[name]*bps+5000)//10000
                price+=merchandise[name]-discount+supplier['shipping_cents']
            candidate=(price,tuple(vector))
            if best is None or candidate<best:best=candidate
            return
        offer=offers[index];name=offer['supplier'];supplier=suppliers[name]
        maximum=min(offer['stock'],remaining[offer['sku']],pool_left[offer['pool']],supplier['max_units']-units[name])
        if not supplier['approved'] or offer['lead_days']>request['deadline_days']:maximum=0
        for resource,per_unit in offer['resources_per_unit'].items():
            if per_unit:maximum=min(maximum,resources[name][resource]//per_unit)
        for amount in range(0,maximum+1,offer['pack_size']):
            remaining[offer['sku']]-=amount;pool_left[offer['pool']]-=amount
            units[name]+=amount;merchandise[name]+=amount*offer['unit_cents']
            for resource,per_unit in offer['resources_per_unit'].items():resources[name][resource]-=amount*per_unit
            visit(index+1,vector+[amount])
            remaining[offer['sku']]+=amount;pool_left[offer['pool']]+=amount
            units[name]-=amount;merchandise[name]-=amount*offer['unit_cents']
            for resource,per_unit in offer['resources_per_unit'].items():resources[name][resource]+=amount*per_unit
    visit(0,[])
    if best is None:return None
    return {'cost_cents':best[0],'allocation':[{'offer_id':o['id'],'units':q} for o,q in zip(offers,best[1]) if q]}
