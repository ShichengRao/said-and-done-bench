"""Independent world-profile oracle; reconstructs endogenous observation histories."""
import copy,itertools


def authority(b):
    records=[r for r in b['routes'] if r['known']<=b['as_of']]
    for left,right in itertools.combinations(records,2):
        if (left['id'],left['revision'])==(right['id'],right['revision']) and left!=right:raise ValueError('conflicting deliveries')
    obligations={o['id']:o for o in b['obligations']+b['commitments']}
    def payload(row):
        if row['obligation'] not in obligations or row['facility'] not in b['facilities']:raise ValueError('unknown route reference')
        item={k:copy.deepcopy(row[k]) for k in ['id','revision','obligation','facility','pledge_cents','windows']};o=obligations[row['obligation']]
        windows=sorted(item['windows'],key=lambda w:(w['from_stage'],w['until_stage'],w['pool']));item['windows']=windows
        starts=[o['pay_stage']]+[w['until_stage'] for w in windows[:-1]]
        if not windows or windows[-1]['until_stage']!=o['repay_stage'] or row['pledge_cents']<o['cents']:raise ValueError('invalid exposure')
        if any(w['from_stage']!=a or w['until_stage']<=a or w['pool'] not in b['collateral'] for a,w in zip(starts,windows)):raise ValueError('invalid window')
        lookup={i['id']:i['stage'] for i in b.get('inspections',[])}
        item['inspection_ids']=sorted(set(row.get('inspection_ids',[])))
        for identity in item['inspection_ids']:
            if identity not in lookup or lookup[identity]<=o['pay_stage']:raise ValueError('unavailable or retroactive inspection')
        return item
    offers=[]
    for identity in sorted({r['id'] for r in records}):
        signed=[r for r in records if r['id']==identity and r['signed']]
        if signed:
            chosen=max(signed,key=lambda r:r['revision'])
            if not chosen['void']:offers.append(payload(chosen))
    commitments=[]
    for c in sorted(b['commitments'],key=lambda c:c['id']):
        matches=[r for r in records if r['id']==c['route'] and r['revision']==c['revision'] and r['signed'] and not r['void'] and r['obligation']==c['id']]
        if not matches:raise ValueError('unknown accepted revision')
        commitments.append(dict(id=c['id'],cents=c['cents'],pay_stage=c['pay_stage'],repay_stage=c['repay_stage'],route=payload(matches[0])))
    return dict(offers=offers,commitments=commitments)


def context(b,auth,selected=()):
    worlds=copy.deepcopy(b['scenarios']);routes=copy.deepcopy(auth['offers'])
    for p in selected:
        if p['kind']=='route':routes.append(copy.deepcopy(p['route']))
        if p['kind']=='inspection':
            for r in routes:
                if r['id']==p['route']:r['inspection_ids']=sorted(set(r.get('inspection_ids',[])+[p['inspection']]))
        for w in worlds:
            if p['kind']=='disclose' and w['id'] in p['scenarios']:w['reveal_stage']=min(w['reveal_stage'],p['stage'])
            if p['kind']=='capacity':w[p['resource']][p['resource_id']][p['stage']]+=p['cents']
    return {'b':b,'auth':auth,'worlds':{w['id']:w for w in worlds},'routes':{r['id']:r for r in routes}}


def history(ctx,world,stage,plan):
    frames=[]
    for t in range(stage+1):
        entitled=set()
        for c in ctx['auth']['commitments']:entitled.update(c['route']['inspection_ids'])
        for o in ctx['b']['obligations']:
            if o['pay_stage']<t:entitled.update(ctx['routes'][plan[o['id']]].get('inspection_ids',[]))
        arrived=tuple(sorted((i['id'],i['results'][world['id']]) for i in ctx['b'].get('inspections',[]) if i['stage']==t and i['id'] in entitled))
        frames.append((world['signals'][t],world['id'] if t>=world['reveal_stage'] else '',arrived))
    return tuple(frames)


def use(ctx,plan,stage):
    loans=[(c,c['route']) for c in ctx['auth']['commitments']]+[(o,ctx['routes'][plan[o['id']]]) for o in ctx['b']['obligations']]
    cash={name:sum(o['cents'] for o,r in loans if r['facility']==name and o['pay_stage']<=stage<o['repay_stage']) for name in sorted(ctx['b']['facilities'])}
    pools={name:sum(r['pledge_cents'] for o,r in loans for win in r['windows'] if win['pool']==name and o['pay_stage']<=stage<o['repay_stage'] and win['from_stage']<=stage<win['until_stage']) for name in sorted(ctx['b']['collateral'])}
    return dict(facilities=cash,collateral=pools)


def valid(ctx,world,plan):
    for stage in range(ctx['b']['horizon']):
        used=use(ctx,plan,stage)
        for category in ('facilities','collateral'):
            if any(n>ctx['worlds'][world][category][key][stage] for key,n in used[category].items()):return False
    return True


def policy_tables(ctx,worlds):
    b=ctx['b'];obs=sorted(b['obligations'],key=lambda o:o['id']);worlds=sorted(worlds)
    vectors=list(itertools.product(*(sorted(r['id'] for r in ctx['routes'].values() if r['obligation']==o['id']) for o in obs)))
    choices=[]
    for w in worlds:
        rows=[]
        for vector in vectors:
            plan=dict(zip([o['id'] for o in obs],vector))
            if valid(ctx,w,plan):rows.append(plan)
        choices.append(rows)
    tables=set()
    for profile in itertools.product(*choices):
        table={};conflict=False
        for w,plan in zip(worlds,profile):
            for stage in range(b['horizon']):
                actions=tuple((o['id'],plan[o['id']]) for o in obs if o['pay_stage']==stage)
                if not actions:continue
                key=(stage,history(ctx,ctx['worlds'][w],stage,plan))
                if key in table and table[key]!=actions:conflict=True;break
                table[key]=actions
            if conflict:break
        if not conflict:tables.add(tuple((stage,observed,actions) for (stage,observed),actions in sorted(table.items())))
    if not tables:return 0,None
    first=[{'stage':stage,'history':[[signal,case,[list(p) for p in reports]] for signal,case,reports in observed],'assignment':[{'obligation':o,'route':r} for o,r in actions]} for stage,observed,actions in min(tables)]
    return len(tables),first


def scenario_audit(ctx,world):
    obs=sorted(ctx['b']['obligations'],key=lambda o:o['id']);count=0;first=None
    for vector in itertools.product(*(sorted(r['id'] for r in ctx['routes'].values() if r['obligation']==o['id']) for o in obs)):
        plan=dict(zip([o['id'] for o in obs],vector))
        if valid(ctx,world,plan):
            count+=1
            if first is None:first=plan
    usage=None
    if first is not None:
        stages=list(range(ctx['b']['horizon']+1));computed=[use(ctx,first,t) for t in stages]
        usage=dict(stages=stages,**{category:{key:[v[category][key] for v in computed] for key in sorted(ctx['b'][category])} for category in ('facilities','collateral')})
    return dict(feasible_plan_count=count,first_plan=None if first is None else [dict(obligation=o['id'],route=first[o['id']]) for o in obs],usage=usage)


def analyze(b):
    auth=authority(b);ctx=context(b,auth);worlds=sorted(ctx['worlds']);number,policy=policy_tables(ctx,worlds);cores=[]
    for size in range(1,len(worlds)+1):
        for subset in itertools.combinations(worlds,size):
            if any(set(core)<=set(subset) for core in cores):continue
            if policy_tables(ctx,subset)[0]==0:cores.append(list(subset))
    requests=[];proposals=sorted(b['proposals'],key=lambda p:p['id'])
    subsets=[[p for p,bit in zip(proposals,bits) if bit] for bits in itertools.product((0,1),repeat=len(proposals))]
    for selected in sorted(subsets,key=lambda chosen:(sum(p['cost'] for p in chosen),len(chosen),[p['id'] for p in chosen])):
        changed=context(b,auth,selected);n,table=policy_tables(changed,worlds)
        if n:
            cost=sum(p['cost'] for p in selected);ids=[p['id'] for p in selected]
            requests.append((cost,len(ids),ids,dict(cost=cost,proposals=ids,policy_count=n,policy=table)));break
    return dict(requested_cents=sum(o['cents'] for o in b['obligations']),frozen_cents=sum(c['cents'] for c in b['commitments']),complete=number>0,authority=auth,scenario_audits={w:scenario_audit(ctx,w) for w in worlds},policy_count=number,policy=policy,infeasible_cores=cores,owner_review=min(requests,key=lambda x:x[:3])[3] if requests else None)

oracle=analyze
