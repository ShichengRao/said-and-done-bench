import copy,random

def small(seed):
    r=random.Random(seed);cs=[{'id':'root','parent':None,'scopes':['read'],'start':0,'end':3,'pool':'root'}];qs=[];routes=[]
    for k in range(1+seed%3):
        leaves=[]
        for choice in range(2):
            n=f'q{k}-{choice}';leaves.append(n);cs.append({'id':n,'parent':'root','scopes':['read'] if r.random()<.85 else [],'start':r.randint(0,1),'end':r.randint(2,3),'pool':r.choice(['a','b'])});routes.append({'id':n,'request':f'q{k}','credentials':['root',n]})
        qs.append({'id':f'q{k}','scopes':['read'],'units':1,'duration':1,'earliest':0,'latest':3,'leaves':leaves})
    return {'schedule':{'slots':[0,1],'workers':{'0':r.randint(1,3),'1':r.randint(1,3)},'budgets':{'root':3,'a':r.randint(0,3),'b':r.randint(0,3)},'credentials':cs,'requests':qs,'routes':routes},'proposals':[{'id':'extra','kind':'budget','pool':'a','units':2,'cost':1}]}

def cases(source):
    for n in range(18):yield f'generated-{n}',small(n)
    b=copy.deepcopy(source)
    for k in ['credentials','requests','routes','slots']:b['schedule'][k].reverse()
    b['proposals'].reverse();yield 'unordered-catalogs',b
    b=copy.deepcopy(source);b['schedule']['budgets']['pool0']+=1;b['schedule']['budgets']['pool4']+=1;yield 'owner-pool-extension',b
    b=copy.deepcopy(source);b['schedule']['workers']['0']+=1;yield 'worker-alone-not-authority',b
    b=copy.deepcopy(source);b['schedule']['credentials'].append(copy.deepcopy(b['schedule']['credentials'][0]));yield 'duplicate-credential',b
    b=copy.deepcopy(source);b['schedule']['routes'][0]['credentials'].append('missing');yield 'unknown-credential',b
    b=small(4);b['schedule']['credentials'][1]['pool']='root';yield 'repeated-root-budget-pool',b

def independent_checks(transform,source):
    result=transform(copy.deepcopy(source));s=source['schedule'];qs={q['id']:q for q in s['requests']}
    assert result['ready'] is False and result['obstruction']==sorted(qs)
    assert all(len(x)==4 for x in result['route_options'].values())
    for name in qs:
        b=copy.deepcopy(source);b['schedule']['requests']=[q for q in s['requests'] if q['id']!=name];b['proposals']=[]
        assert transform(b)['ready'] is True
    assert result['owner_request']['proposal_ids']==['shared-pool-four-lease','shared-pool-zero-lease'] and result['owner_request']['cost']==5
    # A concrete fractional certificate: each request splits half on route 0 at
    # slot 0 and half on route 1 at slot 1. Every shared pool and worker limit fits.
    pool_load={p:0 for p in s['budgets']};worker_load={'0':0,'1':0}
    for name,options in result['route_options'].items():
        for suffix,slot in [('0',0),('1',1)]:
            option=next(o for o in options if o['route']==name+'-'+suffix and o['slot']==slot)
            for pool in option['pools']:pool_load[pool]+=.5
            worker_load[str(slot)]+=.5
    assert all(pool_load[p]<=limit for p,limit in s['budgets'].items())
    assert all(worker_load[k]<=limit for k,limit in s['workers'].items())
    # Forced-use per-ancestor lower bounds also fit every pool.
    for pool,limit in s['budgets'].items():assert sum(qs[name]['units'] for name,options in result['route_options'].items() if all(pool in o['pools'] for o in options))<=limit
    assert sum(s['budgets'][p] for p in s['budgets'] if p!='root')==8

def cli_success_cases():return [('small-3',small(3)),('small-8',small(8))]
