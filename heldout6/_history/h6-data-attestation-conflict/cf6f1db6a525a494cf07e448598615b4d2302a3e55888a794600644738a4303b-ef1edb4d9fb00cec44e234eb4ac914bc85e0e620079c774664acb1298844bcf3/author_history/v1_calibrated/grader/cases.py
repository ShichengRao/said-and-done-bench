import copy,random

def small(seed):
    r=random.Random(seed)
    events=[[{'id':'a1','kind':'owner','document':'d','owner':'y'},{'id':'a2','kind':'owner','document':'d','owner':'x'}],[{'id':'b1','kind':'copy','source':{'kind':'document','id':'d'}},{'id':'b2','kind':'receipt','copy':'b1','audience':'team'}],[{'id':'c1','kind':'grant','owner':r.choice(['x','y']),'audience':'team'},{'id':'c2','kind':'revoke','owner':r.choice(['x','y']),'audience':'team'}]]
    before=[]
    if seed%3==0:before.append(['a1','b1'])
    if seed%5==0:before.append(['b2','a2'])
    return {'evidence':{'owners':{'d':'x'},'grants':[['x','team']] if seed%2 else [],'streams':events,'before':before},'proposals':[{'id':'early-copy','cost':2,'before':[['b1','a1']]},{'id':'late-copy','cost':1,'before':[['a2','b1']]},{'id':'grant-before-receipt','cost':1,'before':[['c1','b2']]},{'id':'receipt-before-revoke','cost':2,'before':[['b2','c2']]}]}

def cases(source):
    for n in range(12):yield 'generated-'+str(n),small(n)
    b=copy.deepcopy(source);b['evidence']['streams'].reverse();b['proposals'].reverse();b['evidence']['before'].reverse();yield 'unordered-containers',b
    b=copy.deepcopy(source);b['evidence']['before'] += [['b2','a2'],['c4','b4']];yield 'verified-owner-ordering',b
    b=copy.deepcopy(source);b['evidence']['before'] += [['a2','b1']];yield 'proven-violation',b
    b=copy.deepcopy(source);b['evidence']['before'].append(['b3','b1']);yield 'cyclic-base-evidence',b
    b=copy.deepcopy(source);b['evidence']['before'].append(['ghost','b1']);yield 'unknown-event',b
    b=copy.deepcopy(source);b['evidence']['streams'][2][3]['id']='a1';yield 'duplicate-event',b

def independent_checks(transform,source):
    result=transform(copy.deepcopy(source))
    assert result['classification']=='missing_order_evidence'
    assert result['safe_count']>0 and result['unsafe_count']>0
    assert result['serialization_count']==result['safe_count']+result['unsafe_count']
    assert result['owner_request']['proposal_ids']==['blue-grant-before-receipt','lineage-before-transfer']
    assert result['owner_request']['cost']==3 and result['owner_request']['serialization_count']>0
    # Proposed signed chronology creates a feasible clean instance under identical rules.
    clean=copy.deepcopy(source)
    clean['evidence']['before'] += [['b2','a2'],['c4','b4']]
    assert transform(clean)['ready'] is True
    bad=copy.deepcopy(source);bad['evidence']['before'].append(['a2','b1'])
    assert transform(bad)['classification']=='proven_violation'

def cli_success_cases():return [('small-1',small(1)),('small-4',small(4))]
