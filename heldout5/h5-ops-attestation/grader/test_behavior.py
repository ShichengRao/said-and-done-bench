import copy,itertools,json,random
from pathlib import Path
import pytest
from release_audit import audit

def fixture(edges,caps):
    ds=sorted(edges);rs=sorted(caps)
    return dict(as_of=80,deployments=[dict(id=d,principal='op',service='svc',region='z',artifact=d,commit=50) for d in ds],grants=[dict(id='g'+r,revision=1,recorded_at=1,principal='owner'+r,role='approve',services=['*'],regions=['z'],start=0,expires=100,revoked_at=None) for r in rs],receipts=[dict(id=r,revision=1,recorded_at=2,principal='owner'+r,grant='g'+r,services=['s*'],regions=['z'],artifacts=[d for d in ds if r in edges[d]],start=10,expires=90,capacity=caps[r]) for r in rs],amendments=[dict(id='remove-'+d,cost=1+i%3,exclude=[d]) for i,d in enumerate(ds)])

def brute(ids,edges,caps):
    candidates=[]
    for choice in itertools.product(*[[None]+edges[d] for d in ids]):
        if any(choice.count(r)>caps[r] for r in caps):continue
        candidates.append([[d,r] for d,r in zip(ids,choice) if r is not None])
    return min(candidates,key=lambda a:(-len(a),a))

def expected(s,edges,caps):
    ids=sorted(edges);assignment=brute(ids,edges,caps);cert=len(assignment)==len(ids);deficiency=None
    for count in range(1,len(ids)+1):
        for ds in itertools.combinations(ids,count):
            rs=sorted({r for d in ds for r in edges[d]});c=sum(caps[r] for r in rs)
            if count>c:deficiency=dict(deployments=list(ds),receipts=rs,demand=count,capacity=c,deficit=count-c);break
        if deficiency:break
    proposals=sorted(s['amendments'],key=lambda q:q['id']);choices=[]
    for bits in itertools.product([False,True],repeat=len(proposals)):
        qs=[q for q,yes in zip(proposals,bits) if yes];exclude=sorted({d for q in qs for d in q['exclude']});remaining=[d for d in ids if d not in exclude];w=brute(remaining,edges,caps)
        if len(w)==len(remaining):choices.append((sum(q['cost'] for q in qs),len(qs),[q['id'] for q in qs],exclude,w))
    b=min(choices) if choices else None;remedy=dict(requests=b[2],cost=b[0],excluded=b[3],assignment=b[4]) if b else None
    return dict(eligible=edges,maximum=len(assignment),required=len(ids),assignment=assignment,certifiable=cert,deficiency=deficiency,remedy=remedy,blocker=None if cert else dict(kind='approval_capacity',deployments=deficiency['deployments'],demand=deficiency['demand'],capacity=deficiency['capacity'],owner_requests=remedy['requests'] if remedy else []))

@pytest.mark.parametrize('seed',range(10))
def test_generated_global_matching_and_remedy(seed):
    rng=random.Random(seed);caps={'r'+str(i):rng.randrange(1,3) for i in range(4)};edges={'d'+str(i):sorted(r for r in caps if rng.random()<.45) for i in range(5)};s=fixture(edges,caps);before=copy.deepcopy(s)
    result=audit(s);want=expected(s,edges,caps);assert result==want and s==before
    if result['remedy']:
        s['deployments']=[d for d in s['deployments'] if d['id'] not in result['remedy']['excluded']]
        remaining={d['id']:edges[d['id']] for d in s['deployments']};s['amendments']=[]
        assert audit(s)==expected(s,remaining,caps) and audit(s)['certifiable']

def test_canonical_fixture_is_collectively_deficient():
    s=json.loads(Path('data/input.json').read_text());result=audit(s)
    assert result==json.loads(Path('/grader/expected_report.json').read_text())
    assert all(result['eligible'].values()) and result['deficiency']['demand']>result['deficiency']['capacity']

def test_greedy_trap_and_canonical_partial_assignment():
    for edges,caps in [({'a':['x','y'],'b':['x']},{'x':1,'y':1}),({'a':['x'],'b':['x'],'c':['y']},{'x':1,'y':1})]:
        s=fixture(edges,caps);assert audit(s)==expected(s,edges,caps)

def test_revision_replay_future_and_conflict():
    edges={'a':['x'],'b':['x']};caps={'x':1};s=fixture(edges,caps)
    s['receipts'] += [dict(s['receipts'][0],revision=2,recorded_at=90,capacity=2),copy.deepcopy(s['receipts'][0])]
    assert audit(s)==expected(s,edges,caps)
    s['as_of']=95;assert audit(s)==expected(s,edges,{'x':2})
    s['receipts'].append(dict(s['receipts'][0],capacity=3))
    with pytest.raises(ValueError):audit(s)

@pytest.mark.parametrize('kind',['self','artifact','grant-start','revocation','receipt-expiry','role','scope'])
def test_historical_authorization_edges(kind):
    s=fixture({'a':['x']},{'x':1})
    if kind=='self':s['deployments'][0]['principal']='ownerx'
    elif kind=='artifact':s['receipts'][0]['artifacts']=[]
    elif kind=='grant-start':s['grants'][0]['start']=11
    elif kind=='revocation':s['grants'][0]['revoked_at']=50
    elif kind=='receipt-expiry':s['receipts'][0]['expires']=50
    elif kind=='role':s['grants'][0]['role']='deploy'
    else:s['grants'][0]['services']=['different']
    assert audit(s)==expected(s,{'a':[]},{'x':1})
    s=fixture({'a':['x']},{'x':1});s['grants'][0]['revoked_at']=51
    assert audit(s)==expected(s,{'a':['x']},{'x':1})


def test_cli_json_contract(tmp_path):
    import subprocess,sys
    cases=[fixture({'a':['x','y'],'b':['x']},{'x':1,'y':1}),fixture({'a':['x'],'b':['x']},{'x':1})]
    for i,s in enumerate(cases):
        edges={d['id']:sorted(r['id'] for r in s['receipts'] if d['id'] in r['artifacts']) for d in s['deployments']};caps={r['id']:r['capacity'] for r in s['receipts']}
        source=tmp_path/('case-'+str(i)+'.json');source.write_text(json.dumps(s))
        run=subprocess.run([sys.executable,'release_audit.py',str(source)],capture_output=True,text=True,timeout=30)
        assert run.returncode==0,run.stderr
        assert json.loads(run.stdout)==expected(s,edges,caps)
