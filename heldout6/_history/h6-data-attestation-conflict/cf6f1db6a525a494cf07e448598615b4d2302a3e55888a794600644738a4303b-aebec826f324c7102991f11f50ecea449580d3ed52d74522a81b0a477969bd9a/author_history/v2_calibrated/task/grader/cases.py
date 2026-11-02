import copy,random


def small(seed):
    rng=random.Random(seed)
    initial=[dict(id='r0',slot='root',parent=None,owner='x',issuer='x',audience='broker',delegate=True),dict(id='l0',slot='leaf',parent='r0',owner='x',issuer='broker',audience='team',delegate=False)]
    streams=[
        [dict(id='a1',kind='owner_cas',document='d',expected=0,owner='y',observed=True),dict(id='a2',kind='owner_cas',document='d',expected=1,owner='x',observed=True)],
        [dict(id='b1',kind='copy',source=dict(kind='document',id='d'),slot='leaf'),dict(id='b2',kind='owner_cas',document='d',expected=rng.randrange(3),owner='z',observed=bool(seed%4==0)),dict(id='b3',kind='receipt',copy='b1',audience='team')],
        [dict(id='c1',kind='revoke',slot='root',expected=0,observed=True),dict(id='c2',kind='grant',expected=1,observed=True,**{k:v for k,v in initial[0].items() if k!='id'}),dict(id='c3',kind='grant',expected=0,observed=bool(seed%3),**{**{k:v for k,v in initial[1].items() if k!='id'},'parent':'c2','issuer':'broker' if seed%5 else 'x'})]]
    before=[]
    if seed%2:before.append(['c2','b3'])
    if seed%3==0:before.append(['a2','b1'])
    if seed%5==0:before.append(['b1','a1'])
    return {'evidence':dict(documents={'d':dict(owner='x',version=0)},slots={'root':dict(generation=0,node='r0'),'leaf':dict(generation=0,node='l0')},capabilities=initial,streams=streams,before=before),'proposals':[dict(id='after-owner-return',cost=2,before=[['a2','b1']]),dict(id='after-child-renewal',cost=1,before=[['c3','b1']]),dict(id='before-root-revoke',cost=1,before=[['b3','c1']])]}


def with_edges(source,edges):
    b=copy.deepcopy(source);b['evidence']['before']+=edges;return b


def late_parent_attempt():
    b=small(1);e=b['evidence']
    e['streams']=[[
        dict(id='attempt',kind='grant',slot='leaf',expected=0,parent='renew',owner='x',issuer='broker',audience='team',delegate=False,observed=False),
        dict(id='cache',kind='copy',source=dict(kind='document',id='d'),slot='leaf'),dict(id='delivery',kind='receipt',copy='cache',audience='team')],
        [dict(id='renew',kind='grant',slot='root',expected=0,parent=None,owner='x',issuer='x',audience='broker',delegate=True,observed=True)]]
    e['before']=[];b['proposals']=[dict(id='deliver-first',cost=1,before=[['delivery','renew']])];return b


def cases(source):
    for n in range(16):yield 'generated-'+str(n),small(n)
    b=copy.deepcopy(source);b['evidence']['streams'].reverse();b['evidence']['capabilities'].reverse();b['proposals'].reverse();yield 'unordered-containers',b
    yield 'verified-owner-ordering',with_edges(source,[['b2','a3'],['a1','b1']])
    yield 'stale-parent-even-after-reissue',with_edges(source,[['b4','c3']])
    yield 'acyclic-but-observation-inconsistent',with_edges(source,[['b2','a3'],['a2','b1']])
    yield 'cyclic-base',with_edges(source,[['b4','b1']])
    yield 'parent-unavailable-failed-grant',late_parent_attempt()
    b=late_parent_attempt();b['evidence']['streams'][0][0]['observed']=True;yield 'parent-availability-success-observation',b
    b=copy.deepcopy(source)
    for row in b['evidence']['documents'].values():row['version']+=7
    for row in b['evidence']['slots'].values():row['generation']+=9
    for stream in b['evidence']['streams']:
        for e in stream:
            if e['kind']=='owner_cas':e['expected']+=7
            if e['kind'] in ('grant','revoke'):e['expected']+=9
    yield 'nonzero-initial-versions',b
    b=copy.deepcopy(source)
    events=[e for s in b['evidence']['streams'] for e in s];rename={e['id']:'event'+str(20-i) for i,e in enumerate(events)}
    for e in events:
        old=e['id'];e['id']=rename[old]
        if e['kind']=='grant' and e['parent'] in rename:e['parent']=rename[e['parent']]
        if e['kind']=='copy' and e['source']['kind']=='copy':e['source']['id']=rename[e['source']['id']]
        if e['kind']=='receipt':e['copy']=rename[e['copy']]
    b['evidence']['before']=[[rename[a],rename[c]] for a,c in b['evidence']['before']]
    for p in b['proposals']:p['before']=[[rename[a],rename[c]] for a,c in p['before']]
    yield 'event-id-relabeling',b
    b=copy.deepcopy(source);b['evidence']['streams'][0].append(dict(id='a4',kind='receipt',copy='b1',audience='broker'));yield 'earliest-unauthorized-receipt',b
    b=copy.deepcopy(source);b['evidence']['slots']['leaf']['node']=None;yield 'missing-captured-capability',b
    b=small(1);e=b['evidence'];e['slots']['leaf']={'generation':4,'node':None};e['streams']=[[dict(id='revoke-empty',kind='revoke',slot='leaf',expected=4,observed=True)]];e['before']=[];b['proposals']=[];yield 'generation-only-empty-revocation',b
    b=copy.deepcopy(b);b['evidence']['streams'][0][0]['observed']=False;yield 'empty-revocation-false-observation',b
    b=copy.deepcopy(source);e=b['evidence'];e['capabilities'][1]['delegate']=True
    e['capabilities'].append(dict(id='grand0',slot='grand',parent='leaf0',owner='alpha',issuer='auditors',audience='archive',delegate=False));e['slots']['grand']=dict(generation=0,node='grand0')
    e['streams'][1][0]['slot']='grand';e['streams'][1][-1]['audience']='archive';e['streams'][2][-1]['delegate']=True
    e['streams'][2].append(dict(id='c4',kind='grant',slot='grand',expected=0,parent='c3',owner='alpha',issuer='auditors',audience='archive',delegate=False,observed=True))
    for p in b['proposals']:
        if p['id']=='copy-after-child-renewal':p['before']=[['c4','b1']]
    yield 'three-level-captured-ancestry',b
    b=small(1);b['evidence']['streams']=[[],[],[]];b['evidence']['before']=[];b['proposals']=[];yield 'empty-sealed-history',b
    b=copy.deepcopy(source);b['evidence']['before'].append(['ghost','b1']);yield 'unknown-event',b
    b=copy.deepcopy(source);b['evidence']['streams'][0].append(copy.deepcopy(b['evidence']['streams'][0][0]));yield 'duplicate-event',b
    b=copy.deepcopy(source);b['evidence']['capabilities'].append(copy.deepcopy(b['evidence']['capabilities'][0]));yield 'duplicate-capability',b
    b=copy.deepcopy(source);b['evidence']['streams'][2][2]['parent']='ghost';yield 'unknown-parent',b
    b=copy.deepcopy(source);b['evidence']['streams'][1][2]['source']['id']='ghost';yield 'unknown-copy',b
    b=copy.deepcopy(source);b['evidence']['streams'][0][0]['slot']='ghost';yield 'unknown-slot',b


def independent_checks(transform,source):
    result=transform(copy.deepcopy(source))
    assert result['classification']=='missing_order_evidence'
    assert (result['serialization_count'],result['safe_count'],result['unsafe_count'])==(187,25,162)
    assert result['first_unsafe']['reason']=='stale_ancestry' and result['first_unsafe']['invalid_ancestor']=='root0'
    assert result['first_unsafe']['capability']=='leaf0' and result['first_unsafe']['lineage']==['b1','b3']
    assert result['owner_request']['proposal_ids']==['capability-diagnostic-before-copy','owner-diagnostic-before-return']
    assert result['owner_request']['cost']==3 and result['owner_request']['serialization_count']==6
    clean=transform(with_edges(source,[['b2','a3'],['a1','b1']]))
    assert clean['ready'] and clean['serialization_count']==6 and clean['owner_request']['proposal_ids']==[]
    bad=transform(with_edges(source,[['b4','c3']]))
    assert bad['classification']=='proven_violation' and bad['unsafe_count']==10
    impossible=transform(with_edges(source,[['b2','a3'],['a2','b1']]))
    assert impossible['classification']=='inconsistent_evidence' and impossible['serialization_count']==0 and impossible['owner_request'] is None


def cli_success_cases():return [('small-1',small(1)),('parent-unavailable',late_parent_attempt())]
