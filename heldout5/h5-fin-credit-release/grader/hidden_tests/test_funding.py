import copy,itertools,json,random
from pathlib import Path
import pytest
from funding import analyze

def fixture():return json.loads(Path('data/request.json').read_text())

def oracle(b):
    def winners(rows):
        seen={};out={}
        for row in sorted([r for r in rows if r['known']<=b['as_of']],key=lambda r:r['revision']):
            key=(row['id'],row['revision'])
            if key in seen and row!=seen[key]:raise ValueError('conflict')
            seen[key]=row;out[row['id']]=row
        return list(out.values())
    holds=[r for r in winners(b['holds']) if not r['void']]
    approvals=[r for r in winners(b['approvals']) if not r['revoked']]
    obs=sorted(b['obligations'],key=lambda x:x['id']);fs={f['id']:f for f in b['facilities']}
    days=sorted({x for o in obs for x in (o['pay_day'],o['repaid_day'])}|{x for h in holds for x in (h['from_day'],h['until_day'])})
    required=sum(o['cents'] for o in obs)
    def solve(ps):
        fl={i:f['limit']+sum(p['facility_delta'].get(i,0) for p in ps) for i,f in fs.items()}
        gl={i:v+sum(p['group_delta'].get(i,0) for p in ps) for i,v in b['groups'].items()}
        alternatives=[]
        for o in obs:
            valid=[]
            for fid,f in fs.items():
                if o['currency']!=f['currency'] or o['beneficiary'] not in f['beneficiaries']:continue
                grants=[a for a in approvals if a['from_day']<=o['pay_day']<a['until_day']]
                grants += [g for p in ps for g in p['grants']]
                if any(a['facility']==fid and a['obligation']==o['id'] and a['cap']>=o['cents'] for a in grants):valid.append(fid)
            alternatives.append(valid+['~'])
        best=None;result=None
        for vector in itertools.product(*alternatives):
            usage={fid:[] for fid in fs};groups={gid:[] for gid in gl}
            for day in days:
                for fid in fs:
                    u=sum(h['cents'] for h in holds if h['facility']==fid and h['from_day']<=day<h['until_day'])
                    u+=sum(o['cents'] for o,f in zip(obs,vector) if f==fid and o['pay_day']<=day<o['repaid_day'])
                    usage[fid].append(u)
                for gid in gl:groups[gid].append(sum(usage[fid][-1] for fid in fs if fs[fid]['group']==gid))
            if any(u>fl[fid] for fid,arr in usage.items() for u in arr) or any(u>gl[gid] for gid,arr in groups.items() for u in arr):continue
            funded=sum(o['cents'] for o,v in zip(obs,vector) if v!='~');cnt=sum(v!='~' for v in vector)
            key=(-funded,-cnt,vector)
            if best is None or key<best:
                best=key;result={'funded_cents':funded,'schedule':[{'obligation':o['id'],'facility':v} for o,v in zip(obs,vector) if v!='~'],'unfunded':[o['id'] for o,v in zip(obs,vector) if v=='~'],'usage':{'days':days,'facilities':usage,'groups':groups}}
        return result
    current=solve([]);possible=[]
    for bits in itertools.product([False,True],repeat=len(b['proposals'])):
        ps=[p for p,v in zip(b['proposals'],bits) if v];x=solve(ps)
        if x['funded_cents']==required:
            ids=sorted(p['id'] for p in ps);cost=sum(p['cost'] for p in ps)
            possible.append(((cost,len(ids),ids),{'cost':cost,'proposals':ids,'schedule':x['schedule']}))
    repair=min(possible,key=lambda x:x[0])[1] if possible else None
    return {'requested_cents':required,'complete':not current['unfunded'],**current,'owner_review':repair}

def test_fixture_coupled_exposure_and_minimum_owner_action():
    b=fixture();before=copy.deepcopy(b);out=analyze(b)
    assert out==oracle(b);assert b==before
    assert out['funded_cents']==1200 and len(out['unfunded'])==1
    assert out['owner_review']['cost']==2 and out['owner_review']['proposals']==['c2']
    # Every obligation and each day separately is feasible; only consistent allocation fails.
    for o in b['obligations']:
        single=copy.deepcopy(b);single['obligations']=[o];single['proposals']=[]
        assert oracle(single)['complete']
    for day in range(0,21):
        slice_=copy.deepcopy(b);slice_['proposals']=[]
        slice_['obligations']=[dict(o,pay_day=day,repaid_day=day+1) for o in b['obligations'] if o['pay_day']<=day<o['repaid_day']]
        assert oracle(slice_)['complete']

def test_authorized_counterfactual_is_feasible_without_proposals():
    b=fixture();b['approvals'].append({'id':'new','revision':1,'known':5,'facility':'f1','obligation':'p5','cap':300,'from_day':0,'until_day':20,'revoked':False});b['proposals']=[]
    out=analyze(b);assert out==oracle(b);assert out['complete'] and out['owner_review']['proposals']==[]

def test_global_choice_not_greedy():
    b=fixture();b['holds']=[];b['proposals']=[];b['groups']={'g1':2000,'g2':400}
    b['facilities'][0]['limit']=400;b['facilities'][1]['limit']=400
    b['obligations']=b['obligations'][:2];b['obligations'][0]['cents']=400;b['obligations'][1]['cents']=400
    b['approvals']=[{'id':str(i),'revision':1,'known':0,'facility':f,'obligation':o,'cap':400,'from_day':0,'until_day':10,'revoked':False} for i,(o,f) in enumerate([('p1','f1'),('p1','f2'),('p2','f1')])]
    out=analyze(b);assert out==oracle(b);assert out['complete'];assert out['schedule'][0]['facility']=='f2'

def test_repayment_boundary_and_hypothetical_change_combinations():
    b=fixture();b['holds']=[];b['facilities']=b['facilities'][:1];b['groups']={'g1':400};b['facilities'][0]['limit']=400
    b['obligations']=b['obligations'][:2];b['obligations'][0]['repaid_day']=5;b['obligations'][1]['pay_day']=5;b['obligations'][1]['repaid_day']=8
    b['approvals']=[a for a in b['approvals'] if a['facility']=='f1'];b['proposals']=[]
    assert analyze(b)==oracle(b);assert analyze(b)['complete']
    b['obligations'][1]['pay_day']=4
    b['proposals']=[{'id':'q1','cost':1,'facility_delta':{'f1':300},'group_delta':{},'grants':[]},{'id':'q2','cost':2,'facility_delta':{},'group_delta':{'g1':300},'grants':[]}]
    out=analyze(b);assert out==oracle(b);assert out['owner_review']['proposals']==['q1','q2']

def test_visible_conflicts_and_future_conflicts():
    b=fixture();x=dict(b['holds'][0],cents=1);b['holds'].append(x)
    with pytest.raises(ValueError):analyze(b)
    b=fixture();b['holds'] += [dict(b['holds'][0],known=20,revision=9),dict(b['holds'][0],known=20,revision=9,cents=1)]
    assert analyze(b)==oracle(b)

def test_generated_temporal_allocations_and_input_orders():
    rng=random.Random(9537)
    for case in range(18):
        b=fixture();b['proposals']=[];b['holds']=[];b['approvals']=[];b['as_of']=4
        b['groups']={'g1':rng.randrange(5,12)*100,'g2':400}
        for f in b['facilities']:f['limit']=rng.randrange(3,8)*100
        for o in b['obligations']:
            o['cents']=rng.randrange(1,5)*100;o['pay_day']=rng.randrange(1,5);o['repaid_day']=o['pay_day']+rng.randrange(1,4)
            for f in b['facilities']:
                if rng.random()<.7:b['approvals'].append({'id':o['id']+'-'+f['id'],'revision':1,'known':rng.randrange(0,7),'facility':f['id'],'obligation':o['id'],'cap':o['cents'],'from_day':0,'until_day':8,'revoked':False})
        expected=oracle(b);before=copy.deepcopy(b);assert analyze(b)==expected;assert b==before
        for name in ['facilities','obligations','approvals']:rng.shuffle(b[name])
        assert analyze(b)==expected


def test_cli_json_contract(tmp_path):
    import subprocess,sys
    canonical=Path('data/request.json')
    expected=json.loads(Path(__file__).with_name('cli_expected.json').read_text())
    alternate=tmp_path/'alternate.json'
    alternate.write_text(json.dumps({'as_of': 1, 'groups': {'g': 5}, 'facilities': [{'id': 'f', 'group': 'g', 'limit': 5, 'currency': 'USD', 'beneficiaries': ['b']}], 'obligations': [{'id': 'p', 'cents': 5, 'pay_day': 1, 'repaid_day': 2, 'currency': 'USD', 'beneficiary': 'b'}], 'holds': [], 'approvals': [{'id': 'a', 'revision': 1, 'known': 0, 'facility': 'f', 'obligation': 'p', 'cap': 5, 'from_day': 0, 'until_day': 10, 'revoked': False}], 'proposals': []}))
    for source,wanted in [(canonical,expected),(alternate,{'requested_cents': 5, 'complete': True, 'funded_cents': 5, 'schedule': [{'obligation': 'p', 'facility': 'f'}], 'unfunded': [], 'usage': {'days': [1, 2], 'facilities': {'f': [5, 0]}, 'groups': {'g': [5, 0]}}, 'owner_review': {'cost': 0, 'proposals': [], 'schedule': [{'obligation': 'p', 'facility': 'f'}]}})]:
        result=subprocess.run([sys.executable,'funding.py',str(source)],capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        assert json.loads(result.stdout)==wanted
