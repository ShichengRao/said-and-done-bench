import copy,random
from itertools import combinations

def small(seed):
    r=random.Random(seed);nodes=['a','b','c'];templates=[{'id':a+b,'nodes':[a,b]} for a,b in combinations(nodes,2)]
    ds=[{'id':f'g{k}','units':r.randint(1,2),'survivors':1+int(seed%7==0),'regions':['eu'],'key':'k','templates':r.sample(['ab','ac','bc'],r.randint(1,3))} for k in range(1+seed%3)]
    return {'placement':{'nodes':[{'id':n,'region':'eu','keys':['k']} for n in nodes],'templates':templates,'datasets':ds,'scenarios':[{'id':f's{i}','down':[n],'capacity':{m:0 if m==n else r.randint(1,4) for m in nodes}} for i,n in enumerate(nodes[:2])]},'proposals':[{'id':'extra','scenario':'s0','node':'b','units':2,'cost':1}]}

def cases(source):
    for n in range(18):yield f'generated-{n}',small(n)
    b=copy.deepcopy(source)
    for key in ['nodes','templates','datasets','scenarios']:b['placement'][key].reverse()
    b['proposals'].reverse();yield 'permuted-catalog',b
    b=copy.deepcopy(source);next(s for s in b['placement']['scenarios'] if s['id']=='gamma-outage')['capacity']['d']+=1;yield 'approved-gamma-lease',b
    b=copy.deepcopy(source);next(s for s in b['placement']['scenarios'] if s['id']=='beta-outage')['capacity']['e']+=1;yield 'approved-beta-lease',b
    b=copy.deepcopy(source);b['placement']['datasets'].append(copy.deepcopy(b['placement']['datasets'][0]));yield 'duplicate-dataset',b
    b=copy.deepcopy(source);b['placement']['datasets'][0]['templates'].append('missing');yield 'unknown-template',b

def independent_checks(transform,source):
    result=transform(copy.deepcopy(source));p=source['placement'];templates={t['id']:t['nodes'] for t in p['templates']};ds={d['id']:d for d in p['datasets']}
    assert result['ready'] is False and all(result['robust_options'].values()) and all(result['scenario_witnesses'].values())
    for s in p['scenarios']:
        row=result['scenario_witnesses'][s['id']]
        assert set(row)==set(ds)
        for name,t in row.items():assert len(set(templates[t])-set(s['down']))>=ds[name]['survivors']
        for node,cap in s['capacity'].items():
            if node not in s['down']:assert sum(ds[name]['units'] for name,t in row.items() if node in templates[t])<=cap
    for name,opts in result['robust_options'].items():
        for t in opts:
            for s in p['scenarios']:
                live=set(templates[t])-set(s['down']);assert len(live)>=ds[name]['survivors'];assert all(ds[name]['units']<=s['capacity'][n] for n in live)
    assert result['owner_request']['proposal_ids']==['gamma-d-lease'] and result['owner_request']['cost']==2
    for name in ds:
        b=copy.deepcopy(source);b['placement']['datasets']=[d for d in b['placement']['datasets'] if d['id']!=name];b['proposals']=[]
        assert transform(b)['ready'] is True
    # Eligible-region aggregate capacity passes even with ineligible node f removed.
    for s in p['scenarios']:assert sum(v for n,v in s['capacity'].items() if n!='f')>=6

def cli_success_cases():return [(f'generated-{n}',small(n)) for n in [1,8]]
