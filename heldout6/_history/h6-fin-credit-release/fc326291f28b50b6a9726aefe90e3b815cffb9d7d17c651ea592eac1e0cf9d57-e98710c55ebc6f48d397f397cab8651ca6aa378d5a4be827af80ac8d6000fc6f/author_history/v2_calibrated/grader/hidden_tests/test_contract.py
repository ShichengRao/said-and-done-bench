import copy,json,subprocess,sys
from pathlib import Path
import pytest
from funding import analyze
from independent import oracle
from fixtures import approved,cases


def request():return json.loads(Path('data/request.json').read_text())


def test_production_independent_policy_table_certificate():
    b=request();result=analyze(b);assert result==oracle(b)
    assert result['policy_count']==0 and not result['complete']
    assert {n:a['feasible_plan_count'] for n,a in result['scenario_audits'].items()}=={'X-low':1,'X-balanced':2,'Y-high':2,'Y-balanced':2}
    assert result['infeasible_cores']==[['X-balanced','X-low'],['Y-balanced','Y-high']]
    assert result['owner_review']['cost']==3 and result['owner_review']['policy_count']==8
    assert result['owner_review']['proposals']==['X-authenticated-leaf-at-2','Y-authenticated-leaf-at-1']
    frozen=result['authority']['commitments'][0]['route'];offer=next(r for r in result['authority']['offers'] if r['id']=='F-route')
    assert (frozen['revision'],frozen['facility'],frozen['windows'][0]['pool'])==(1,'A','P')
    assert (offer['revision'],offer['facility'],offer['windows'][0]['pool'])==(2,'B','R')


def test_generated_and_metamorphic_models_with_input_preservation():
    for label,b in cases(request()):
        before=copy.deepcopy(b)
        try:expected=oracle(copy.deepcopy(b))
        except ValueError:
            with pytest.raises(ValueError):analyze(b)
        else:assert analyze(b)==expected,label
        assert b==before,label


def test_information_deadlines_and_real_owner_counterfactuals():
    b=request();early=approved(b,['X-authenticated-leaf-at-2','Y-authenticated-leaf-at-1']);late=approved(b,['X-authenticated-leaf-at-2','Y-authenticated-leaf-at-2'])
    r=analyze(early);assert r['complete'] and r['policy_count']==8 and r['owner_review']['proposals']==[]
    assert analyze(late)['policy_count']==0
    for option in ['approve-neutral-route','additional-P-capacity']:
        alternate=approved(b,[option]);result=analyze(alternate);assert result==oracle(alternate) and result['complete']


def test_perfect_recall_after_a_common_pending_message():
    b=request();b['commitments'][0]['revision']=2;result=analyze(b);assert result==oracle(b) and result['policy_count']==1
    stage2=[n for n in result['policy'] if n['stage']==2]
    assert len(stage2)==2 and all(n['history'][-1]==['pending',''] for n in stage2)
    assert {n['assignment'][0]['route'] for n in stage2}=={'O2-P','O2-Q'}


def test_cli_alternate_input_json():
    import tempfile
    b=approved(request(),['approve-neutral-route'])
    with tempfile.TemporaryDirectory() as folder:
        p=Path(folder)/'alternate.json';p.write_text(json.dumps(b))
        run=subprocess.run([sys.executable,'funding.py',str(p)],capture_output=True,text=True,timeout=30)
    assert run.returncode==0 and json.loads(run.stdout)==analyze(b),run.stderr
