"""Authority reconstruction and backward nonanticipating policy search."""
from copy import deepcopy
from functools import lru_cache
from itertools import combinations,product


def _authority(b):
    obligations={o['id']:o for o in b['obligations']+b['commitments']}
    visible={}
    for row in b['routes']:
        if row['known']>b['as_of']:continue
        key=(row['id'],row['revision'])
        if key in visible and row!=visible[key]:raise ValueError('conflicting visible revision')
        visible[key]=row
    def normalized(row):
        if row['obligation'] not in obligations or row['facility'] not in b['facilities']:raise ValueError('unknown route reference')
        o=obligations[row['obligation']];windows=sorted(deepcopy(row['windows']),key=lambda w:(w['from_stage'],w['until_stage'],w['pool']))
        cursor=o['pay_stage']
        for w in windows:
            if w['pool'] not in b['collateral'] or w['from_stage']!=cursor or w['until_stage']<=cursor:raise ValueError('invalid pledge partition')
            cursor=w['until_stage']
        if cursor!=o['repay_stage'] or row['pledge_cents']<o['cents']:raise ValueError('invalid pledge exposure')
        return dict(id=row['id'],revision=row['revision'],obligation=row['obligation'],facility=row['facility'],pledge_cents=row['pledge_cents'],windows=windows)
    selected={}
    for row in visible.values():
        if row['signed'] and (row['id'] not in selected or selected[row['id']]['revision']>row['revision']):selected[row['id']]=row
    offers=[normalized(row) for _,row in sorted(selected.items()) if not row['void']]
    frozen=[]
    for c in sorted(b['commitments'],key=lambda x:x['id']):
        row=visible.get((c['route'],c['revision']))
        if row is None or not row['signed'] or row['void'] or row['obligation']!=c['id']:raise ValueError('unavailable accepted revision')
        frozen.append({k:c[k] for k in ['id','cents','pay_stage','repay_stage']}|{'route':normalized(row)})
    return {'offers':offers,'commitments':frozen}


def _context(b,authority,proposals=()):
    worlds={s['id']:deepcopy(s) for s in b['scenarios']};offers=deepcopy(authority['offers'])
    for p in proposals:
        if p['kind']=='disclose':
            for name in p['scenarios']:worlds[name]['reveal_stage']=min(worlds[name]['reveal_stage'],p['stage'])
        elif p['kind']=='capacity':
            for world in worlds.values():world[p['resource']][p['resource_id']][p['stage']]+=p['cents']
        else:offers.append(deepcopy(p['route']))
    return {'horizon':b['horizon'],'obligations':sorted(deepcopy(b['obligations']),key=lambda o:o['id']),'frozen':deepcopy(authority['commitments']),'worlds':worlds,'routes':{r['id']:r for r in offers},'facilities':sorted(b['facilities']),'collateral':sorted(b['collateral'])}


def _usage(ctx,assignment,stage):
    usage={'facilities':dict.fromkeys(ctx['facilities'],0),'collateral':dict.fromkeys(ctx['collateral'],0)}
    rows=[(c,c['route']) for c in ctx['frozen']]+[(o,ctx['routes'][assignment[o['id']]]) for o in ctx['obligations'] if o['id'] in assignment]
    for o,r in rows:
        if o['pay_stage']<=stage<o['repay_stage']:
            usage['facilities'][r['facility']]+=o['cents']
            for w in r['windows']:
                if w['from_stage']<=stage<w['until_stage']:usage['collateral'][w['pool']]+=r['pledge_cents']
    return usage


def _fits(ctx,world,assignment,stage):
    usage=_usage(ctx,assignment,stage);scenario=ctx['worlds'][world]
    return all(amount<=scenario[kind][name][stage] for kind in usage for name,amount in usage[kind].items())


def _choices(ctx,o):return sorted(r['id'] for r in ctx['routes'].values() if r['obligation']==o['id'])


def _history(world,stage):
    return tuple((world['signals'][k],world['id'] if k>=world['reveal_stage'] else '') for k in range(stage+1))


def _policy_json(policy):
    if policy is None:return None
    return [{'stage':stage,'history':[list(x) for x in history],'assignment':[{'obligation':o,'route':r} for o,r in actions]} for stage,history,actions in policy]


def _policies(ctx,world_ids):
    @lru_cache(None)
    def descend(stage,worlds,prior):
        if stage==ctx['horizon']:return 1,()
        groups={}
        for world in worlds:groups.setdefault(_history(ctx['worlds'][world],stage),[]).append(world)
        due=[o for o in ctx['obligations'] if o['pay_stage']==stage]
        total=1;policy=[]
        for history,group in sorted(groups.items()):
            count=0;best=None
            for vector in product(*[_choices(ctx,o) for o in due]):
                assignment=dict(prior);actions=tuple((o['id'],r) for o,r in zip(due,vector));assignment.update(actions)
                if not all(_fits(ctx,w,assignment,stage) for w in group):continue
                number,suffix=descend(stage+1,tuple(group),tuple(sorted(assignment.items())))
                if not number:continue
                nodes=tuple(sorted((((stage,history,actions),) if due else ())+suffix))
                count+=number
                if best is None or nodes<best:best=nodes
            if not count:return 0,None
            total*=count;policy.extend(best)
        return total,tuple(sorted(policy))
    return descend(0,tuple(sorted(world_ids)),())


def _scenario_audit(ctx,name):
    best=None;count=0;obs=ctx['obligations']
    for vector in product(*[_choices(ctx,o) for o in obs]):
        assignment=dict(zip([o['id'] for o in obs],vector))
        if not all(_fits(ctx,name,assignment,k) for k in range(ctx['horizon'])):continue
        count+=1
        if best is None:best=assignment
    usage=None
    if best is not None:
        values=[_usage(ctx,best,k) for k in range(ctx['horizon']+1)]
        usage={'stages':list(range(ctx['horizon']+1)),**{kind:{name:[v[kind][name] for v in values] for name in ctx[kind]} for kind in ['facilities','collateral']}}
    return {'feasible_plan_count':count,'first_plan':None if best is None else [{'obligation':o['id'],'route':best[o['id']]} for o in obs],'usage':usage}


def analyze(bundle):
    b=bundle;authority=_authority(b);ctx=_context(b,authority);worlds=sorted(ctx['worlds'])
    count,policy=_policies(ctx,worlds);cores=[]
    if not count:
        for size in range(1,len(worlds)+1):
            for subset in combinations(worlds,size):
                if any(set(core)<=set(subset) for core in cores):continue
                if not _policies(ctx,subset)[0]:cores.append(list(subset))
    candidates=[];proposals=sorted(b['proposals'],key=lambda p:p['id'])
    subsets=[chosen for size in range(len(proposals)+1) for chosen in combinations(proposals,size)]
    subsets.sort(key=lambda chosen:(sum(p['cost'] for p in chosen),len(chosen),[p['id'] for p in chosen]))
    for selected in subsets:
        modified=_context(b,authority,selected);number,witness=_policies(modified,worlds)
        if number:
            ids=[p['id'] for p in selected];cost=sum(p['cost'] for p in selected)
            candidates.append((cost,len(ids),ids,{'cost':cost,'proposals':ids,'policy_count':number,'policy':_policy_json(witness)}));break
    return {'requested_cents':sum(o['cents'] for o in b['obligations']),'frozen_cents':sum(c['cents'] for c in b['commitments']),'complete':count>0,'authority':authority,'scenario_audits':{name:_scenario_audit(ctx,name) for name in worlds},'policy_count':count,'policy':_policy_json(policy),'infeasible_cores':cores,'owner_review':min(candidates,key=lambda x:x[:3])[3] if candidates else None}

if __name__=='__main__':
    import json,sys
    print(json.dumps(analyze(json.load(open(sys.argv[1])))))
