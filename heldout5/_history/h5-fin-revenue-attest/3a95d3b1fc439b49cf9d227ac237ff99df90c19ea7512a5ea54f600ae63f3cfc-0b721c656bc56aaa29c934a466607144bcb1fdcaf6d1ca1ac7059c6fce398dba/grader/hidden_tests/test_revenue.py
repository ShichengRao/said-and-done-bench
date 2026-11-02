import copy,json,random
from pathlib import Path
from fractions import Fraction
import pytest
from revenue import rollforward

def bundle():return {'as_of':5,'open_day':5,'close_day':8,'requested_cents':0,'terms':[],'progress':[],'invoices':[],'posted':[],'proposals':[]}
def term(id='t',price=101,obs=None):return dict(id=id,revision=1,known=0,contract='c',effective=0,price_cents=price,obligations=obs or {'a':{'weight':1,'units':4},'b':{'weight':1,'units':2}},signed=True)
def event(id='p',o='a',units=1,at=3):return dict(id=id,revision=1,known=0,contract='c',obligation=o,at=at,units=units,void=False)
def test_supplied_source_linked_catchup_and_joint_remedy():
    b=json.loads(Path('data/request.json').read_text());old=copy.deepcopy(b);r=rollforward(b)
    assert b==old and (r['period_cents'],r['requested_cents'],r['variance_cents'],r['complete'])==(364,524,-160,False)
    assert r['owner_review']=={'cost':5,'proposals':['r1','r2'],'period_cents':524}
    c=r['contracts'][0];assert c['terms']=={'id':'t2','revision':1} and c['deferred_cents']==302
    assert c['obligations'][0]=={'id':'a','allocated_cents':302,'completed_units':5,'recognized_cents':151,'opening_cents':210,'period_cents':-59,'progress_sources':['p1'],'opening_sources':['j0','j7']}
    assert [(c['period_cents'],c['recognized_cents']) for c in r['contracts']]==[(245,605),(62,362),(57,267)]
    # A signed source correction, evaluated without modifying the original bundle, could support the request.
    corrected=copy.deepcopy(b);corrected['progress'] += b['proposals'][0]['progress']+b['proposals'][1]['progress']
    r=rollforward(corrected);assert r['complete'] and r['owner_review']=={'cost':0,'proposals':[],'period_cents':524}

def test_exact_allocation_half_up_retirement_and_negative_catchup():
    b=bundle();b['terms']=[term()];b['progress']=[event(),event('q','b',1)];b['posted']=[dict(id='j',contract='c',obligation='a',period_end=5,cents=40),dict(id='k',contract='c',obligation='retired',period_end=4,cents=20)]
    r=rollforward(b);a,z,ret=r['contracts'][0]['obligations']
    assert (a['allocated_cents'],a['recognized_cents'],a['period_cents'])==(51,13,-27)
    assert (z['allocated_cents'],z['recognized_cents'])==(50,25)
    assert ret['recognized_cents']==0 and ret['period_cents']==-20 and r['period_cents']==-22
    b['progress'].append(event('over','a',20));assert rollforward(b)['contracts'][0]['obligations'][0]['recognized_cents']==51

def test_resolve_revisions_before_void_time_and_invoice_credits():
    b=bundle();b['terms']=[term()];p=event();b['progress']=[p,dict(p,revision=2,at=9),dict(p,revision=3,known=6,units=3)]
    i=dict(id='i',revision=1,known=0,contract='c',at=3,cents=100,void=False)
    b['invoices']=[i,dict(i,revision=2,cents=-7)];r=rollforward(b)
    assert r['period_cents']==0 and r['contracts'][0]['billed_cents']==-7 and r['contracts'][0]['invoice_sources']==['i']
    b['progress'].append(dict(p,revision=3,known=5,void=True));assert rollforward(b)['period_cents']==0
    b['terms'].append(dict(term('new',999),effective=8,signed=False));assert rollforward(b)['contracts'][0]['price_cents']==101

def test_conflicts_missing_terms_and_invalid_counterfactual():
    b=bundle();p=event();b['terms']=[term()];b['progress']=[p,dict(p,units=2),dict(p,revision=2,units=3)]
    with pytest.raises(ValueError):rollforward(b)
    b['progress']=[p,dict(p,revision=2,known=6),dict(p,revision=2,known=6,units=3)];assert rollforward(b)['period_cents']==13
    b['terms'].append(term('ambiguous'))
    with pytest.raises(ValueError):rollforward(b)
    b['terms']=[]
    with pytest.raises(ValueError):rollforward(b)
    b['terms']=[term()];b['progress']=[event(o='unknown')]
    with pytest.raises(ValueError):rollforward(b)
    b['progress']=[event(units=-1)]
    with pytest.raises(ValueError):rollforward(b)
    b['progress']=[p];b['requested_cents']=0;b['proposals']=[{'id':'x','cost':0,'progress':[event('minus',units=-2)]}]
    assert rollforward(b)['owner_review'] is None

def test_generated_fraction_oracle_and_reordering():
    rng=random.Random(611)
    for case in range(24):
        b=bundle();price=rng.randrange(0,2000);obs={chr(97+i):{'weight':rng.randrange(1,6),'units':rng.randrange(1,12)} for i in range(rng.randrange(1,6))}
        b['terms']=[term(price=price,obs=obs)];total=sum(o['weight'] for o in obs.values());fractions={k:Fraction(price*o['weight'],total) for k,o in obs.items()};allocated={k:int(v) for k,v in fractions.items()}
        for k in sorted(obs,key=lambda k:(-(fractions[k]-int(fractions[k])),k))[:price-sum(allocated.values())]:allocated[k]+=1
        expected=[]
        for i,(k,o) in enumerate(obs.items()):
            units=rng.randrange(o['units']+3);opening=rng.randrange(0,80);b['progress'].append(event('p'+k,k,units));b['posted'].append(dict(id='j'+k,contract='c',obligation=k,period_end=5,cents=opening))
            cents=int(Fraction(allocated[k]*min(units,o['units']),o['units'])+Fraction(1,2))
            expected.append((k,allocated[k],min(units,o['units']),cents,opening,cents-opening))
        r=rollforward(b);lines=r['contracts'][0]['obligations'];assert [(x['id'],x['allocated_cents'],x['completed_units'],x['recognized_cents'],x['opening_cents'],x['period_cents']) for x in lines]==expected
        assert r['period_cents']==sum(x[-1] for x in expected)
        b['requested_cents']=r['period_cents'];r=rollforward(b);assert r['complete'] and r['owner_review']['proposals']==[]
        rng.shuffle(b['progress']);rng.shuffle(b['posted']);assert rollforward(b)==r


def test_cli_json_contract(tmp_path):
    import subprocess,sys
    canonical=Path('data/request.json')
    expected=json.loads(Path(__file__).with_name('cli_expected.json').read_text())
    alternate=tmp_path/'alternate.json'
    alternate.write_text(json.dumps({'as_of': 3, 'open_day': 2, 'close_day': 3, 'requested_cents': 2, 'terms': [{'id': 't', 'revision': 1, 'known': 0, 'contract': 'c', 'effective': 0, 'price_cents': 5, 'obligations': {'a': {'weight': 1, 'units': 2}}, 'signed': True}], 'progress': [{'id': 'p', 'revision': 1, 'known': 0, 'contract': 'c', 'obligation': 'a', 'at': 1, 'units': 1, 'void': False}], 'invoices': [{'id': 'i', 'revision': 1, 'known': 0, 'contract': 'c', 'at': 1, 'cents': 4, 'void': False}], 'posted': [{'id': 'j', 'contract': 'c', 'obligation': 'a', 'period_end': 2, 'cents': 1}], 'proposals': []}))
    for source,wanted in [(canonical,expected),(alternate,{'contracts': [{'id': 'c', 'terms': {'id': 't', 'revision': 1}, 'price_cents': 5, 'billed_cents': 4, 'recognized_cents': 3, 'deferred_cents': 1, 'period_cents': 2, 'invoice_sources': ['i'], 'obligations': [{'id': 'a', 'allocated_cents': 5, 'completed_units': 1, 'recognized_cents': 3, 'opening_cents': 1, 'period_cents': 2, 'progress_sources': ['p'], 'opening_sources': ['j']}]}], 'requested_cents': 2, 'period_cents': 2, 'variance_cents': 0, 'complete': True, 'owner_review': {'cost': 0, 'proposals': [], 'period_cents': 2}})]:
        result=subprocess.run([sys.executable,'revenue.py',str(source)],capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        assert json.loads(result.stdout)==wanted
