import copy,itertools,random


def approved(source,ids):
    b=copy.deepcopy(source)
    for p in [p for p in b['proposals'] if p['id'] in ids]:
        if p['kind']=='disclose':
            for s in b['scenarios']:
                if s['id'] in p['scenarios']:s['reveal_stage']=min(s['reveal_stage'],p['stage'])
        elif p['kind']=='capacity':
            for s in b['scenarios']:s[p['resource']][p['resource_id']][p['stage']]+=p['cents']
        elif p['kind']=='inspection':
            row=max((r for r in b['routes'] if r['id']==p['route'] and r['signed'] and r['known']<=b['as_of']),key=lambda r:r['revision'])
            row['inspection_ids']=sorted(set(row.get('inspection_ids',[])+[p['inspection']]))
        else:b['routes'].append(dict(**copy.deepcopy(p['route']),revision=1,known=b['as_of'],signed=True,void=False))
    b['proposals']=[p for p in b['proposals'] if p['id'] not in ids]
    return b


def restrict(source,names):
    b=copy.deepcopy(source);b['scenarios']=[s for s in b['scenarios'] if s['id'] in names]
    for p in b['proposals']:
        if p['kind']=='disclose':p['scenarios']=[n for n in p['scenarios'] if n in names]
    b['proposals']=[p for p in b['proposals'] if p['kind']!='disclose' or p['scenarios']]
    return b


def recall(source):
    b=copy.deepcopy(source);b['proposals']=[]
    for r in b['routes']:r['inspection_ids']=[]
    b['routes'][0]['inspection_ids']=['inspect-X','inspect-Y']
    for i in b['inspections']:i['stage']=1
    return b


def cases(source):
    for seed in range(16):
        rng=random.Random(6300+seed);b=copy.deepcopy(source);b['proposals']=[]
        for i in b['inspections']:
            i['stage']=rng.choice([2,3]);i['results']={w['id']:rng.choice(['red','blue']) for w in b['scenarios']}
        for r in b['routes']:
            if r['obligation']=='O1':r['inspection_ids']=[i['id'] for i in b['inspections'] if rng.choice([0,1])]
        for w in b['scenarios']:
            for kind in ['facilities','collateral']:
                for key in w[kind]:w[kind][key][3]=100*rng.randint(1,4)
        yield 'generated-endogenous-'+str(seed),b
    b=copy.deepcopy(source)
    for key in ['obligations','commitments','facilities','collateral','routes','scenarios','proposals','inspections']:b[key].reverse()
    for r in b['routes']:r['windows'].reverse();r['inspection_ids'].reverse()
    yield 'unordered-deliveries-and-windows',b
    for ids in [['P-enable-X'],['Q-enable-Y'],['P-enable-X','Q-enable-Y'],['all-at-3'],['extra-P']]:yield 'approved-'+','.join(ids),approved(source,ids)
    b=copy.deepcopy(source)
    for r in b['routes']:r['inspection_ids']=[]
    yield 'no-existing-inspections',b
    b=copy.deepcopy(source)
    for i in b['inspections']:i['stage']=3
    yield 'all-inspections-arrive-too-late',b
    b=copy.deepcopy(source)
    for i in b['inspections']:i['results']={k:'same-partition' for k in i['results']}
    yield 'authorized-result-does-not-identify-world',b
    b=copy.deepcopy(source)
    for r in b['routes']:r['inspection_ids']*=2
    yield 'duplicate-entitlements-normalize',b
    b=copy.deepcopy(source);b['proposals']=[];b['routes'][0]['inspection_ids']=['inspect-X']
    newer=copy.deepcopy(b['routes'][0]);newer.update(revision=2,known=15,inspection_ids=[])
    b['routes']=[newer if r['id']=='F-route' and r['revision']==2 else r for r in b['routes']]
    yield 'accepted-inspection-not-newer-offer',b
    yield 'perfect-recall-of-once-delivered-inspection',recall(source)
    b=copy.deepcopy(source);b['commitments']=[];b['routes']=[r for r in b['routes'] if r['obligation']!='F'];yield 'no-prior-commitment',b
    b=copy.deepcopy(source);b['routes'][0]['windows']=[dict(from_stage=0,until_stage=4,pool='R')];yield 'no-substitution',b
    b=copy.deepcopy(source);b['commitments'][0]['revision']=2;yield 'different-actual-accepted-revision',b
    b=copy.deepcopy(source)
    for o in b['obligations']:
        if o['id']=='O2':o['pay_stage']=1
    for r in b['routes']:
        if r['obligation']=='O2':r['windows'][0]['from_stage']=1
    yield 'joint-funding-batch-before-inspection',b
    for n in range(1,4):
        for group in itertools.combinations([w['id'] for w in source['scenarios']],n):yield 'restricted-'+','.join(group),restrict(source,set(group))
    b=copy.deepcopy(source);b['obligations']=[];b['routes']=[r for r in b['routes'] if r['obligation']=='F'];b['proposals']=[];yield 'empty-new-request-retains-frozen-exposure',b
    b=copy.deepcopy(source);row=copy.deepcopy(next(r for r in b['routes'] if r['id']=='O2-Q' and r['revision']==3));row['pledge_cents']+=1;b['routes'].append(row);yield 'future-conflict-ignored',b
    b=copy.deepcopy(source);row=copy.deepcopy(next(r for r in b['routes'] if r['id']=='O2-Q' and r['revision']==2));row['pledge_cents']+=1;b['routes'].append(row);yield 'visible-draft-conflict',b
    b=copy.deepcopy(source);b['routes'][0]['windows'][-1]['until_stage']=3;yield 'invalid-current-partition',b
    b=copy.deepcopy(source);b['commitments'][0]['revision']=99;yield 'unknown-accepted-revision',b
    b=copy.deepcopy(source);b['routes'][0]['inspection_ids']=['unknown'];yield 'unknown-accepted-inspection',b
    b=copy.deepcopy(source);next(i for i in b['inspections'] if i['id']=='inspect-X')['stage']=1;yield 'retroactive-current-inspection',b
    b=copy.deepcopy(source);row=copy.deepcopy(next(r for r in b['routes'] if r['id']=='F-route' and r['revision']==2));row.update(revision=3,known=20,void=True);b['routes'].append(row);yield 'void-current-offer-keeps-accepted-contract',b
    # Real optional new route still falls within every owner-subset profile bound.
    b=copy.deepcopy(source);row=copy.deepcopy(next(r for r in b['routes'] if r['id']=='O2-P'));row['id']='O2-owner';row['facility']='C';row['inspection_ids']=[]
    b['proposals'].append(dict(id='new-route',cost=4,kind='route',route={k:v for k,v in row.items() if k not in ['revision','known','signed','void']}));yield 'prospective-route-expanded-profile-domain',b
