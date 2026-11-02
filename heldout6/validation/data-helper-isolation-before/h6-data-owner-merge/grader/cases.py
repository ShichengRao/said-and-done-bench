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

def change_grant(source,entity,mode):
    b=copy.deepcopy(source)
    row=next(r for r in b['history']['entries'] if r['kind']=='handoff' and r['entity']==entity)
    if mode=='remove':b['history']['entries'].remove(row)
    else:
        if mode=='broaden':
            row=copy.deepcopy(row);row['entity']+='-other-boundary';b['history']['entries'].append(row)
        row['value']['boundary']=1-row['value']['boundary']
        row['effective']=row['value']['boundary']
    return b


def source_for_groups(source,keep):
    members={n for group in keep for n in ([group] if group=='warehouse' else [group,group+'-history0'])}
    b=copy.deepcopy(source);rows=[]
    for row in b['history']['entries']:
        if row['kind']=='record' and row['entity'] not in members:continue
        if row['kind']=='merge' and not {row['value']['left'],row['value']['right']}<=members:continue
        if row['kind']=='handoff' and row['value']['record'] not in members:continue
        rows.append(row)
    b['history']['entries']=rows
    b['proposals']=[p for p in b['proposals'] if p['kind']=='capacity' or p['group'] in keep]
    return b


def approve_middle_capacity(source):
    b=copy.deepcopy(source)
    for row in b['history']['entries']:
        if row['kind']=='capacity' and row['entity']=='alpha' and row['revision']==2:row['value']['units']=4
    return b


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
    yield 'approved-middle-capacity',approve_middle_capacity(source)
    for entity in ['accounts-window-transfer','tickets-early-transfer']:
        yield 'approved-middle-capacity-without-'+entity,change_grant(approve_middle_capacity(source),entity,'remove')
    for entity in ['accounts-window-transfer','tickets-early-transfer']:
        for mode in ['remove','shift','broaden']:
            yield entity+'-'+mode,change_grant(source,entity,mode)
    from itertools import combinations
    for size in range(3):
        for keep in combinations(['accounts','contacts','tickets'],size):
            yield 'proper-core-subset-'+'-'.join(keep),source_for_groups(source,set(keep)|{'warehouse'})


def independent_checks(transform,source):
    from itertools import combinations,product
    result=transform(copy.deepcopy(source));p=result['resolved_plan']
    assert result['ready'] is False and result['obstruction']==['accounts','contacts','tickets']
    assert all(result['phase_witnesses']) and all(result['local_paths'].values())
    assert {g['id']:g['load'] for g in p['groups']}=={'accounts':[2,2,1],'contacts':[2,1,2],'tickets':[1,2,2],'warehouse':[1,1,1]}
    assert {g['id']:g['handoffs'] for g in p['groups']}=={'accounts':[[1,'alpha','beta']],'contacts':[],'tickets':[[0,'beta','alpha']],'warehouse':[]}
    assert p['capacity']=={'alpha':[3,3,3],'beta':[3,3,3],'gamma':[1,1,1]}
    groups={g['id']:g for g in p['groups']}
    wanted_paths={'accounts':[['alpha','alpha','beta'],['beta','beta','beta']],
                  'contacts':[['alpha','alpha','alpha'],['beta','beta','beta']],
                  'tickets':[['beta','alpha','alpha'],['beta','beta','beta']],
                  'warehouse':[['gamma','gamma','gamma']]}
    assert result['local_paths']==wanted_paths
    for k,row in enumerate(result['phase_witnesses']):
        assert set(row)==set(groups)
        assert all(row[name] in g['allowed'][k] for name,g in groups.items())
        for owner,cap in p['capacity'].items():assert sum(groups[name]['load'][k] for name,o in row.items() if o==owner)<=cap[k]
    # A second, literal eight-row certificate: never call the planner/oracle.
    names=['accounts','contacts','tickets'];feasible=[]
    for matrix in product(*(wanted_paths[n] for n in names)):
        if all(sum(groups[n]['load'][k] for n,path in zip(names,matrix) if path[k]==owner)<=3 for k in range(3) for owner in ['alpha','beta']):feasible.append(matrix)
    assert feasible==[]
    # Every proper subset of the three-group obstruction remains feasible with
    # the independent warehouse retained; filter all reference-bearing inputs.
    for size in range(3):
        for keep in combinations(names,size):assert transform(source_for_groups(source,set(keep)|{'warehouse'}))['ready'] is True
    # Half of each legal path meets the relaxed capacities. Doubled units avoid
    # floating arithmetic and preserve the actual allowed paths/qualifications.
    for k in range(3):
        for owner in ['alpha','beta']:
            assert sum(groups[n]['load'][k] for n in names for path in wanted_paths[n] if path[k]==owner)<=6
    wanted_remedy={'accounts':['alpha','alpha','beta'],'contacts':['beta','beta','beta'],'tickets':['beta','beta','alpha'],'warehouse':['gamma','gamma','gamma']}
    assert result['owner_request']=={'proposal_ids':['tickets-late-handoff'],'cost':2,'assignment':wanted_remedy}
    for cutoff in [7,12]:
        b=copy.deepcopy(source);b['history']['cutoff']=cutoff;assert transform(b)['ready'] is True
    for entity in ['accounts-window-transfer','tickets-early-transfer']:
        for mode in ['shift','broaden']:assert transform(change_grant(source,entity,mode))['ready'] is True
    # The approved remedy genuinely uses current authority; its tickets grant
    # alone is insufficient after removing the accounts boundary-1 permission.
    b=change_grant(source,'accounts-window-transfer','remove');b['history']['cutoff']=12
    assert transform(b)['ready'] is False
    # The alternative phase-1 capacity approval requires BOTH current grants.
    b=approve_middle_capacity(source);assert transform(b)['ready'] is True
    for entity in ['accounts-window-transfer','tickets-early-transfer']:
        assert transform(change_grant(b,entity,'remove'))['ready'] is False


def cli_success_cases():return [('small-2',small(2)),('small-9',small(9))]
