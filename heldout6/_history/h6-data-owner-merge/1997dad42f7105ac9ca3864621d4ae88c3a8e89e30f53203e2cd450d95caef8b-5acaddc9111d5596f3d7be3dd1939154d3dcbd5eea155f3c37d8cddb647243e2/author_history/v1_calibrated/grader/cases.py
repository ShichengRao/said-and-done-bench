import copy,random

def old_small(seed):
    r=random.Random(seed);groups=[]
    for n in range(1+seed%4):
        groups.append({'id':f'g{n}','members':[f'record{n}'],'load':[r.randint(1,2) for _ in range(3)],'allowed':[[o for o in ['a','b'] if r.random()<.8] or ['a'] for _ in range(3)],'handoffs':[[k,a,b] for k in range(2) for a,b in [('a','b'),('b','a')] if r.random()<.3]})
    return {'plan':{'phases':3,'capacity':{'a':[r.randint(1,4) for _ in range(3)],'b':[r.randint(1,4) for _ in range(3)]},'groups':groups},'proposals':[{'id':'extra','kind':'capacity','owner':'a','phase':1,'units':2,'cost':1}]}


def encode(plan):
    entries=[]
    for g in plan['groups']:
        for k in range(plan['phases']):entries.append({'kind':'record','entity':g['id'],'revision':k+1,'recorded':1,'effective':k,'approved':True,'value':{'units':g['load'][k],'owners':g['allowed'][k]}})
        for n,(k,a,c) in enumerate(g['handoffs']):entries.append({'kind':'handoff','entity':g['id']+str(n),'revision':1,'recorded':1,'effective':0,'approved':True,'value':{'record':g['id'],'boundary':k,'from':a,'to':c,'active':True}})
    for owner,caps in plan['capacity'].items():
        for k,value in enumerate(caps):entries.append({'kind':'capacity','entity':owner,'revision':k+1,'recorded':1,'effective':k,'approved':True,'value':{'units':value}})
    return {'phases':plan['phases'],'cutoff':10,'entries':entries}
def small(seed):
    old=old_small(seed);return {'history':encode(old['plan']),'proposals':old['proposals']}

def cases(source):
    for n in range(20):yield f'generated-{n}',small(n)
    b=copy.deepcopy(source);b['history']['entries'].reverse();b['proposals'].reverse();yield 'permuted-history',b
    b=copy.deepcopy(source);b['history']['cutoff']=12;yield 'new-owner-approval-arrived',b
    b=copy.deepcopy(source)
    for r in b['history']['entries']:
        if r['kind']=='capacity' and r['entity']=='alpha' and r['revision']==4:r['approved']=True
    yield 'capacity-request-approved',b
    b=copy.deepcopy(source);b['history']['entries'].append(copy.deepcopy(b['history']['entries'][0]));yield 'duplicate-revision',b
    b=copy.deepcopy(source);b['history']['cutoff']=7;yield 'earlier-authorized-freeze',b

def independent_checks(transform,source):
    result=transform(copy.deepcopy(source));p=result['resolved_plan']
    assert result['ready'] is False and result['obstruction']==['accounts','contacts','tickets']
    assert all(result['phase_witnesses']) and all(result['local_paths'].values())
    assert {g['id']:g['load'] for g in p['groups']}=={'accounts':[2,2,1],'contacts':[2,1,2],'tickets':[1,2,2],'warehouse':[1,1,1]}
    assert all(g['handoffs']==[] for g in p['groups'])
    assert p['capacity']['alpha']==[3,3,3]
    groups={g['id']:g for g in p['groups']}
    for k,row in enumerate(result['phase_witnesses']):
        assert set(row)==set(groups)
        assert all(row[name] in g['allowed'][k] for name,g in groups.items())
        for owner,cap in p['capacity'].items():assert sum(groups[name]['load'][k] for name,o in row.items() if o==owner)<=cap[k]
    for name,paths in result['local_paths'].items():
        for path in paths:assert all(a==c or [k,a,c] in groups[name]['handoffs'] for k,(a,c) in enumerate(zip(path,path[1:])))
    assert result['owner_request']['proposal_ids']==['tickets-late-handoff']
    for cutoff in [7,12]:
        b=copy.deepcopy(source);b['history']['cutoff']=cutoff;assert transform(b)['ready'] is True
    for k in range(3):assert sum(g['load'][k]/2 for g in p['groups'] if g['id']!='warehouse')<=3

def cli_success_cases():return [('small-2',small(2)),('small-9',small(9))]
