import copy,itertools,json,random
from pathlib import Path
import pytest
from payouts import reconcile

def empty():return {'as_of':5,'payout_day':5,'settlements':[],'transfers':[],'attestations':[],'proposals':[]}
def lot(id,cents,rail='ach',owner='a'):return dict(id='s-'+id,revision=1,known=0,lot=id,owner=owner,currency='USD',rail=rail,gross=cents,refund=0,fee=0,void=False)
def att(id,cap,rails=['ach'],owner='a'):return dict(id=id,revision=1,known=0,owner=owner,currencies=['USD'],rails=list(rails),cap=cap,from_day=0,until_day=9,revoked=False)
def transfer(id,source,target,day):return dict(id=id,revision=1,known=0,source=source,target=target,effective=day,void=False)
def maxflow(lots,ats):
    # Independent augmenting path oracle, unlike the reference's Hall-subset formula.
    cap={};adj={}
    def edge(a,b,c):cap[a,b]=c;cap[b,a]=0;adj.setdefault(a,[]).append(b);adj.setdefault(b,[]).append(a)
    for i,l in enumerate(lots):edge('S','l'+str(i),l['cents'])
    for j,a in enumerate(ats):edge('a'+str(j),'T',a['cap'])
    for i,l in enumerate(lots):
        for j,a in enumerate(ats):
            if l['owner']==a['owner'] and l['currency'] in a['currencies'] and l['rail'] in a['rails']:edge('l'+str(i),'a'+str(j),100000)
    total=0
    while True:
        prev={'S':None};queue=['S']
        for x in queue:
            for y in adj.get(x,[]):
                if y not in prev and cap[x,y]>0:prev[y]=x;queue.append(y)
        if 'T' not in prev:return total
        path=[];y='T'
        while prev[y] is not None:path.append((prev[y],y));y=prev[y]
        amount=min(cap[e] for e in path);total+=amount
        for x,y in path:cap[x,y]-=amount;cap[y,x]+=amount

def test_request_reconstructs_and_proves_shared_coverage():
    b=json.loads(Path('data/request.json').read_text());before=copy.deepcopy(b);r=reconcile(b)
    assert b==before and r['requested_cents']==1600 and r['covered_cents']==1500 and not r['complete']
    assert r['lots'][1]=={'id':'l2','owner':'x','currency':'USD','rail':'wire','cents':300,'sources':['s2','s7'],'owner_path':['a','x']}
    assert r['lots'][2]['owner_path']==['b','y','x']
    assert r['deficiency']=={'lots':['l2','l4'],'attestations':['t1'],'required_cents':600,'capacity_cents':500,'shortfall_cents':100}
    assert r['owner_review']=={'cost':2,'proposals':['r3']}
    # Neither total caps nor a missing per-lot permission exposes the shortage.
    live=[b['attestations'][i] for i in [0,1,2]]
    assert sum(a['cap'] for a in live)>1600
    assert all(maxflow([l],live)==l['cents'] for l in r['lots'])
    assert maxflow(r['lots'],live)==1500

def test_authorized_counterfactual_and_combination_remedy():
    b=empty();b['settlements']=[lot('x',9),lot('y',7,'wire')];b['attestations']=[att('a',6),att('b',4,['wire'])]
    b['proposals']=[{'id':'p','cost':2,'attestations':[{'id':'n','owner':'a','currencies':['USD'],'rails':['ach'],'cap':3}]},{'id':'q','cost':1,'attestations':[{'id':'m','owner':'a','currencies':['USD'],'rails':['wire'],'cap':3}]}]
    assert reconcile(b)['owner_review']=={'cost':3,'proposals':['p','q']}
    for p in b['proposals']:
        for a in p['attestations']:b['attestations'].append(att(a['id'],a['cap'],a['rails']))
    r=reconcile(b);assert r['complete'] and r['deficiency'] is None and r['owner_review']=={'cost':0,'proposals':[]}

def test_revision_before_filter_and_temporal_chain():
    b=empty();s=lot('x',10);b['settlements']=[s,dict(s,revision=2,gross=99,void=True),dict(s,revision=3,known=9,gross=80)]
    assert reconcile(b)['lots']==[]
    b['settlements']=[s,dict(id='negative',revision=1,known=0,lot='x',owner='a',currency='USD',rail='ach',gross=0,refund=3,fee=2,void=False)]
    b['transfers']=[transfer('a','a','b',5),transfer('b','b','c',4),transfer('future','a','d',6)]
    b['attestations']=[att('t',5,owner='c')];r=reconcile(b)
    assert r['complete'] and r['lots'][0]['cents']==5 and r['lots'][0]['owner_path']==['a','b','c']
    b['attestations'].append(dict(b['attestations'][0],revision=2,revoked=True))
    assert reconcile(b)['covered_cents']==0

def test_semantic_rejections_and_cutoff():
    b=empty();s=lot('x',10);b['settlements']=[s,dict(s,gross=20),dict(s,revision=2,gross=30)]
    with pytest.raises(ValueError):reconcile(b)
    b['settlements']=[s,dict(s,revision=2,known=7),dict(s,revision=2,known=7,gross=50)]
    assert reconcile(b)['requested_cents']==10
    b['transfers']=[transfer('one','a','b',2),transfer('two','a','b',2)]
    with pytest.raises(ValueError):reconcile(b)
    b['transfers']=[transfer('one','a','b',2),transfer('two','b','a',3)]
    with pytest.raises(ValueError):reconcile(b)
    b['transfers']=[];b['settlements']=[s,dict(s,id='other',owner='b')]
    with pytest.raises(ValueError):reconcile(b)
    b['settlements']=[dict(s,gross=0,fee=1)]
    with pytest.raises(ValueError):reconcile(b)

def test_generated_flow_and_proposal_minimum():
    rng=random.Random(720)
    for case in range(22):
        b=empty();b['settlements']=[lot('l'+str(i),rng.randrange(1,15),rng.choice(['ach','wire','card']),rng.choice(['a','b'])) for i in range(rng.randrange(2,7))]
        b['attestations']=[att('t'+str(i),rng.randrange(1,20),rng.sample(['ach','wire','card'],rng.randrange(1,4)),rng.choice(['a','b'])) for i in range(5)]
        b['proposals']=[{'id':'p'+str(i),'cost':i+1,'attestations':[{'id':'u'+str(i),'owner':owner,'currencies':['USD'],'rails':['ach','wire','card'],'cap':50}]} for i,owner in enumerate(['a','b'])]
        before=copy.deepcopy(b);r=reconcile(b);assert b==before
        assert r['covered_cents']==maxflow(r['lots'],b['attestations'])
        candidates=[]
        for bits in itertools.product([0,1],repeat=2):
            chosen=[b['proposals'][i] for i,v in enumerate(bits) if v];ats=b['attestations']+[a for p in chosen for a in p['attestations']]
            if maxflow(r['lots'],ats)==r['requested_cents']:candidates.append((sum(p['cost'] for p in chosen),len(chosen),sorted(p['id'] for p in chosen)))
        best=min(candidates);assert r['owner_review']=={'cost':best[0],'proposals':best[2]}
        if r['deficiency']:
            d=r['deficiency'];subset=[l for l in r['lots'] if l['id'] in d['lots']]
            assert sum(l['cents'] for l in subset)-maxflow(subset,b['attestations'])==d['shortfall_cents']
        rng.shuffle(b['settlements']);rng.shuffle(b['attestations']);assert reconcile(b)==r


def test_minimum_deficiency_certificate_and_proposal_id_tie():
    b=empty();b['settlements']=[lot('x',5),lot('y',3,'wire')];b['attestations']=[att('a',2),att('b',3,['wire'])]
    b['proposals']=[{'id':pid,'cost':1,'attestations':[{'id':'u-'+pid,'owner':'a','currencies':['USD'],'rails':['ach'],'cap':3}]} for pid in ['z','p']]
    r=reconcile(b)
    assert r['deficiency']=={'lots':['x'],'attestations':['a'],'required_cents':5,'capacity_cents':2,'shortfall_cents':3}
    assert r['owner_review']=={'cost':1,'proposals':['p']}
    b['settlements'].reverse();b['proposals'].reverse();assert reconcile(b)==r


def test_cli_json_contract(tmp_path):
    import subprocess,sys
    canonical=Path('data/request.json')
    expected=json.loads(Path(__file__).with_name('cli_expected.json').read_text())
    alternate=tmp_path/'alternate.json'
    alternate.write_text(json.dumps({'as_of': 3, 'payout_day': 3, 'settlements': [{'id': 's', 'revision': 1, 'known': 0, 'lot': 'l', 'owner': 'o', 'currency': 'USD', 'rail': 'ach', 'gross': 7, 'refund': 1, 'fee': 1, 'void': False}], 'transfers': [{'id': 'm', 'revision': 1, 'known': 0, 'source': 'o', 'target': 'o2', 'effective': 3, 'void': False}], 'attestations': [{'id': 'a', 'revision': 1, 'known': 0, 'owner': 'o2', 'currencies': ['USD'], 'rails': ['ach'], 'cap': 5, 'from_day': 0, 'until_day': 4, 'revoked': False}], 'proposals': []}))
    for source,wanted in [(canonical,expected),(alternate,{'lots': [{'id': 'l', 'owner': 'o2', 'currency': 'USD', 'rail': 'ach', 'cents': 5, 'sources': ['s'], 'owner_path': ['o', 'o2']}], 'requested_cents': 5, 'covered_cents': 5, 'complete': True, 'deficiency': None, 'owner_review': {'cost': 0, 'proposals': []}})]:
        result=subprocess.run([sys.executable,'payouts.py',str(source)],capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        assert json.loads(result.stdout)==wanted
