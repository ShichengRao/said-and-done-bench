import copy,random

def small(seed):
    r=random.Random(seed);groups=[]
    for n in range(1+seed%4):
        groups.append({'id':f'g{n}','members':[f'record{n}'],'load':[r.randint(1,2) for _ in range(3)],'allowed':[[o for o in ['a','b'] if r.random()<.8] or ['a'] for _ in range(3)],'handoffs':[[k,a,b] for k in range(2) for a,b in [('a','b'),('b','a')] if r.random()<.3]})
    return {'plan':{'phases':3,'capacity':{'a':[r.randint(1,4) for _ in range(3)],'b':[r.randint(1,4) for _ in range(3)]},'groups':groups},'proposals':[{'id':'extra','kind':'capacity','owner':'a','phase':1,'units':2,'cost':1}]}

def cases(source):
    for n in range(20):yield f'generated-{n}',small(n)
    b=copy.deepcopy(source);b['plan']['groups'].reverse();b['proposals'].reverse()
    for g in b['plan']['groups']:
        for row in g['allowed']:row.reverse()
    yield 'input-permutations',b
    b=copy.deepcopy(source);next(g for g in b['plan']['groups'] if g['id']=='tickets')['handoffs'].append([1,'beta','alpha']);yield 'approved-directional-handoff',b
    b=copy.deepcopy(source);b['plan']['capacity']['alpha'][0]+=1;yield 'approved-one-phase-capacity',b
    b=copy.deepcopy(source);next(g for g in b['plan']['groups'] if g['id']=='tickets')['handoffs'].append([0,'beta','alpha']);yield 'wrong-boundary-does-not-help',b
    b=copy.deepcopy(source);b['plan']['groups'].append(copy.deepcopy(b['plan']['groups'][0]));yield 'duplicate-group',b
    b=copy.deepcopy(source);b['plan']['groups'][0]['allowed'][0].append('absent');yield 'unknown-owner',b

def independent_checks(transform,source):
    b=copy.deepcopy(source);result=transform(b)
    assert result['ready'] is False and result['obstruction']==['accounts','contacts','tickets']
    assert all(result['phase_witnesses']) and all(result['local_paths'].values())
    # Independently validate witnesses rather than trusting their presence.
    groups={g['id']:g for g in b['plan']['groups']}
    for k,row in enumerate(result['phase_witnesses']):
        assert set(row)==set(groups)
        assert all(row[name] in g['allowed'][k] for name,g in groups.items())
        for owner,cap in b['plan']['capacity'].items():assert sum(groups[name]['load'][k] for name,o in row.items() if o==owner)<=cap[k]
    for name,paths in result['local_paths'].items():
        assert paths
        for path in paths:
            assert all(path[k] in groups[name]['allowed'][k] for k in range(3))
            assert all(a==c or [k,a,c] in groups[name]['handoffs'] for k,(a,c) in enumerate(zip(path,path[1:])))
    assert result['owner_request']['proposal_ids']==['tickets-late-handoff'] and result['owner_request']['cost']==2
    for excluded in ['accounts','contacts','tickets']:
        sub=copy.deepcopy(source);sub['plan']['groups']=[g for g in sub['plan']['groups'] if g['id']!=excluded];sub['proposals']=[]
        assert transform(sub)['ready'] is True
    # Fractional split relaxation: half each core group's load fits both alpha/beta.
    for k in range(3):assert sum(g['load'][k]/2 for g in source['plan']['groups'] if g['id']!='warehouse')<=3

def cli_success_cases():return [(f'small-{n}',small(n)) for n in [2,9]]
