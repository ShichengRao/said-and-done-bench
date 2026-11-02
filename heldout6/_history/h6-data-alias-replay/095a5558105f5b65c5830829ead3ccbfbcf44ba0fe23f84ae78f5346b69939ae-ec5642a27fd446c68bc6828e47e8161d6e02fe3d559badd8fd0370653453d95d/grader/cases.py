import copy,random

def small(seed):
    r=random.Random(seed);shards=['a','b','c'];base={s:seed%3 for s in shards};nexts=dict(base)
    b={'snapshot':{'cut':base,'customers':[{'tenant':'x','id':'one','seats':10,'tier':'base','active':True,'extra':{'keep':[1,2]}},{'tenant':'x','id':'two','seats':20,'tier':'plus','active':True}],'aliases':[{'tenant':'x','alias':'live','customer':'one'}]},'request':{},'transactions':[],'deliveries':[]}
    for n in range(5):
        chosen=r.sample(shards,r.randint(1,2));parts=[]
        for s in chosen:
            nexts[s]+=1;parts.append({'shard':s,'first':nexts[s],'last':nexts[s]})
        ops=[{'kind':'adjust','tenant':'x','alias':'live','delta':n+1}]
        if n==2:ops.insert(0,{'kind':'bind','tenant':'x','alias':'live','customer':'two'})
        t={'id':f't{n}','order':n,'decision':r.choice(['commit','commit','abort','unresolved']),'parts':parts,'depends':[f't{n-1}'] if n and r.random()<.65 else [],'operations':ops};b['transactions'].append(t)
        for p in parts:
            if r.random()<.85:b['deliveries'].append({'shard':p['shard'],'offset':p['first'],'transaction':t['id']})
    b['request']={'upper':nexts,'minimum':dict(base) if seed%2 else dict(nexts)}
    r.shuffle(b['transactions']);r.shuffle(b['deliveries'])
    return b

def cases(source):
    for seed in range(32):yield f'generated-{seed}',small(seed)
    b=copy.deepcopy(source);b['request']['minimum']=dict(b['request']['upper']);yield 'floor-not-achievable',b
    b=copy.deepcopy(source);b['transactions'].reverse();b['deliveries'].reverse();b['snapshot']['customers'].reverse();b['snapshot']['aliases'].reverse();yield 'permuted-evidence',b
    b=copy.deepcopy(source);b['deliveries'].append(dict(b['deliveries'][0]));yield 'duplicate-delivery',b
    b=copy.deepcopy(source);b['deliveries'][0]['transaction']='unknown';yield 'unknown-transaction',b
    b=copy.deepcopy(source);b['deliveries'].append({**b['deliveries'][0],'transaction':'m41'});yield 'conflicting-delivery',b
    b=copy.deepcopy(source);b['transactions'].append(copy.deepcopy(b['transactions'][0]));yield 'duplicate-manifest',b
    b=copy.deepcopy(source);next(t for t in b['transactions'] if t['id']=='m41')['operations'][0]['delta']=-100;yield 'negative-seats',b
    b=copy.deepcopy(source);next(t for t in b['transactions'] if t['id']=='m41')['operations'][0]['alias']='absent';yield 'missing-binding',b
    b=small(1);b['transactions']=[{'id':'prepare','order':1,'decision':'unresolved','parts':[{'shard':'a','first':2,'last':2}],'depends':[],'operations':[]},{'id':'dependent','order':2,'decision':'commit','parts':[{'shard':'b','first':2,'last':2}],'depends':['prepare'],'operations':[]}];b['deliveries']=[{'shard':'a','offset':2,'transaction':'prepare'},{'shard':'b','offset':2,'transaction':'dependent'}];b['request']={'upper':{'a':2,'b':2,'c':1},'minimum':{'a':1,'b':1,'c':1}};yield 'cross-shard-dependency-only',b
    b=copy.deepcopy(source);t=next(t for t in b['transactions'] if t['id']=='m96');t['parts'][0]['last']=5;b['request']['upper'][t['parts'][0]['shard']]=5;b['deliveries'].append({'shard':t['parts'][0]['shard'],'offset':5,'transaction':'m96'});yield 'multi-offset-part',b

def independent_checks(transform,source):
    result=transform(copy.deepcopy(source))
    assert result['cut']=={'archive':2,'crm':2,'tickets':2}
    assert result['included']==['m41','m58','m63'] and result['applied']==['m41','m58']
    assert result['deferred']==['m77','m82','m96'] and result['ready'] is True
    assert [(c['tenant'],c['id'],c['seats']) for c in result['customers']]==[('cedar','c1',13),('cedar','c2',4),('larch','c1',2)]
    assert result['delivery_duplicates']==1

def cli_success_cases():
    return [(f'variant-{n}',small(n)) for n in [2,7,19]]
