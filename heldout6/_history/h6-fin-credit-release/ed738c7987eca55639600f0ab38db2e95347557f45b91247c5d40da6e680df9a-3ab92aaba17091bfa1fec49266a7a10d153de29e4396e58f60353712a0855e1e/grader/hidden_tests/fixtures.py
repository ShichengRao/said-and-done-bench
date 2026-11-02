import copy,random


def approved(source,ids):
    b=copy.deepcopy(source);chosen=[p for p in b['proposals'] if p['id'] in ids]
    for p in chosen:
        if p['kind']=='disclose':
            for s in b['scenarios']:
                if s['id'] in p['scenarios']:s['reveal_stage']=min(s['reveal_stage'],p['stage'])
        elif p['kind']=='capacity':
            for s in b['scenarios']:s[p['resource']][p['resource_id']][p['stage']]+=p['cents']
        else:b['routes'].append(dict(**copy.deepcopy(p['route']),revision=1,known=b['as_of'],signed=True,void=False))
    # Already-approved route IDs must not remain prospective additions.
    b['proposals']=[p for p in b['proposals'] if p['id'] not in ids]
    return b


def restrict(source,names):
    b=copy.deepcopy(source);b['scenarios']=[s for s in b['scenarios'] if s['id'] in names]
    for p in b['proposals']:
        if p['kind']=='disclose':p['scenarios']=[n for n in p['scenarios'] if n in names]
    b['proposals']=[p for p in b['proposals'] if p['kind']!='disclose' or p['scenarios']]
    return b


def small(seed):
    rng=random.Random(seed);repay=2 if seed%3==0 else 3
    obligations=[dict(id='a',cents=rng.randint(1,2),pay_stage=1,repay_stage=3),dict(id='b',cents=rng.randint(1,2),pay_stage=2,repay_stage=3)]
    def route(name,ob,facility,pool,revision=1):return dict(id=name,revision=revision,known=1,signed=True,void=False,obligation=ob['id'],facility=facility,pledge_cents=ob['cents'],windows=[dict(from_stage=ob['pay_stage'],until_stage=ob['repay_stage'],pool=pool)])
    frozen=dict(id='f',cents=1,pay_stage=0,repay_stage=repay,route='f-route',revision=1)
    rows=[route('f-route',frozen,'A','P'),route('f-route',frozen,'B','Q',2)]
    for o in obligations:rows += [route(o['id']+'-p',o,'A','P'),route(o['id']+'-q',o,'B','Q')]
    rows.append(copy.deepcopy(rows[-1]))
    scenarios=[dict(id='s'+str(i),signals=['open','group'+str(i) if seed%3==0 else 'pending','closed'],reveal_stage=2,facilities={'A':[3,3,rng.randint(2,5)],'B':[3,3,rng.randint(2,5)]},collateral={'P':[4,4,rng.randint(2,6)],'Q':[4,4,rng.randint(2,6)]}) for i in range(2)]
    new=route('a-owner',obligations[0],'A','Q');new={k:v for k,v in new.items() if k not in ['revision','known','signed','void']}
    return dict(as_of=4,horizon=3,obligations=obligations,commitments=[frozen],facilities=['A','B'],collateral=['P','Q'],routes=rows,scenarios=scenarios,proposals=[dict(id='early',cost=1,kind='disclose',scenarios=['s0','s1'],stage=1),dict(id='pool',cost=2,kind='capacity',resource='collateral',resource_id='P',stage=2,cents=3),dict(id='route',cost=3,kind='route',route=new)])


def cases(source):
    for seed in range(12):yield 'generated-'+str(seed),small(seed)
    b=copy.deepcopy(source)
    for key in ['obligations','commitments','facilities','collateral','routes','scenarios','proposals']:b[key].reverse()
    for r in b['routes']:r['windows'].reverse()
    yield 'unordered-deliveries-and-windows',b
    yield 'approved-selective-disclosure',approved(source,['X-authenticated-leaf-at-2','Y-authenticated-leaf-at-1'])
    yield 'both-leaves-still-too-late',approved(source,['X-authenticated-leaf-at-2','Y-authenticated-leaf-at-2'])
    yield 'approved-neutral-route',approved(source,['approve-neutral-route'])
    yield 'approved-P-capacity',approved(source,['additional-P-capacity'])
    b=copy.deepcopy(source);b['commitments'][0]['revision']=2;yield 'different-real-accepted-commitment-perfect-recall',b
    b=copy.deepcopy(source);b['routes']=[r for r in b['routes'] if r['obligation']!='F'];b['commitments']=[];yield 'no-prior-commitment',b
    b=copy.deepcopy(source);b['routes']=[r for r in b['routes'] if not (r['id']=='O2-H' and r['revision']==2)];yield 'older-offer-really-current',b
    b=copy.deepcopy(source)
    for row in b['routes']:
        if row['id']=='F-route':row['windows'][0]['until_stage']=2
    b['commitments'][0]['repay_stage']=2;yield 'accepted-exposure-repaid-at-new-funding-boundary',b
    b=copy.deepcopy(source)
    for o in b['obligations']:
        if o['id']=='O2':o['pay_stage']=1
    for r in b['routes']:
        if r['obligation']=='O2':min(r['windows'],key=lambda w:w['from_stage'])['from_stage']=1
    for p in b['proposals']:
        if p['kind']=='route':p['route']['windows'][0]['from_stage']=1
    yield 'joint-funding-batch',b
    for names in [{'X-low','X-balanced'},{'Y-high','Y-balanced'},{'X-low','Y-high'},{'X-balanced'}]:yield 'restricted-'+','.join(sorted(names)),restrict(source,names)
    b=small(1);b['obligations']=[];b['routes']=[r for r in b['routes'] if r['obligation']=='f'];b['proposals']=[p for p in b['proposals'] if p['kind']!='route'];yield 'empty-new-request-retains-frozen-exposure',b
    b=copy.deepcopy(source);row=copy.deepcopy(next(r for r in b['routes'] if r['id']=='O2-H' and r['revision']==4));row['pledge_cents']+=1;b['routes'].append(row);yield 'future-conflict-ignored',b
    b=copy.deepcopy(source);row=copy.deepcopy(next(r for r in b['routes'] if r['id']=='O2-H' and r['revision']==3));row['pledge_cents']+=1;b['routes'].append(row);yield 'visible-draft-conflict',b
    b=copy.deepcopy(source)
    for r in b['routes']:
        if r['id']=='O2-H' and r['revision']==2:r['windows'][-1]['until_stage']=3
    yield 'invalid-current-partition',b
    b=copy.deepcopy(source);b['commitments'][0]['revision']=99;yield 'unknown-accepted-revision',b
    b=copy.deepcopy(source);row=copy.deepcopy(next(r for r in b['routes'] if r['id']=='F-route' and r['revision']==2));row.update(revision=3,known=20,void=True);b['routes'].append(row);yield 'void-current-offer-keeps-accepted-contract',b
