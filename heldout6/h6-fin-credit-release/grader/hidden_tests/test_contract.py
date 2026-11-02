import copy,itertools,json,subprocess,sys
from pathlib import Path
import pytest
from funding import analyze

def _trusted_support(filename):
    # Keep evaluator helpers out of the candidate's Python import namespace.
    import importlib.util
    source=Path(__file__).resolve().with_name(filename)
    spec=importlib.util.spec_from_file_location('_trusted_support_'+source.stem,source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

_independent=_trusted_support('independent.py');oracle=_independent.oracle
_fixtures=_trusted_support('fixtures.py');approved,cases,recall,restrict=_fixtures.approved,_fixtures.cases,_fixtures.recall,_fixtures.restrict


def request():return json.loads(Path('data/request.json').read_text())


def test_production_independent_policy_certificate():
    b=request();r=analyze(b);assert r==oracle(b)
    assert r['policy_count']==0 and not r['complete']
    assert {n:a['feasible_plan_count'] for n,a in r['scenario_audits'].items()}=={'X-cash':4,'X-pledge':3,'Y-cash':4,'Y-pledge':3}
    assert r['infeasible_cores']==[['X-cash','X-pledge','Y-cash','Y-pledge']]
    assert r['owner_review']['cost']==2 and r['owner_review']['policy_count']==6 and r['owner_review']['proposals']==['P-enable-X']
    frozen=r['authority']['commitments'][0]['route'];offer=next(x for x in r['authority']['offers'] if x['id']=='F-route')
    assert (frozen['revision'],frozen['facility'],[w['pool'] for w in frozen['windows']])==(1,'A',['R','P'])
    assert (offer['revision'],offer['facility'],offer['windows'][0]['pool'])==(2,'B','Q')


def test_generated_and_metamorphic_models_with_input_preservation():
    for label,b in cases(request()):
        before=copy.deepcopy(b)
        try:expected=oracle(copy.deepcopy(b))
        except ValueError:
            with pytest.raises(ValueError):analyze(b)
        else:assert analyze(b)==expected,label
        assert b==before,label


def test_four_way_core_has_feasible_proper_subsets():
    b=request()
    for group in itertools.combinations([s['id'] for s in b['scenarios']],3):
        r=analyze(restrict(b,set(group)));assert r==oracle(restrict(b,set(group))) and r['policy_count']==6 and r['infeasible_cores']==[]


def test_real_inspection_grants_and_receipt_timing():
    b=request()
    for ids,count in [(['P-enable-X'],6),(['Q-enable-Y'],6),(['P-enable-X','Q-enable-Y'],12),(['extra-P'],24)]:
        x=approved(b,ids);r=analyze(x);assert r==oracle(x) and r['policy_count']==count and r['owner_review']['proposals']==[]
    x=approved(b,['P-enable-X'])
    for i in x['inspections']:i['stage']=3
    assert analyze(x)==oracle(x) and analyze(x)['policy_count']==0
    x=copy.deepcopy(b)
    for r in x['routes']:
        if r['obligation']=='O1':r['inspection_ids']=['inspect-X','inspect-Y']
    assert analyze(x)==oracle(x) and analyze(x)['policy_count']==12


def test_policy_domain_and_perfect_recall_are_action_dependent():
    b=approved(request(),['P-enable-X']);r=analyze(b);assert r==oracle(b)
    assert len(r['policy'])==9
    assert r['policy'][0]['assignment']==[dict(obligation='O1',route='O1-P')]
    assert all(len(n['history'][2][2])==2 for n in r['policy'] if n['stage']==2)
    assert all(n['history'][-1][2]==[] for n in r['policy'] if n['stage']==3)
    x=recall(request());out=analyze(x);assert out==oracle(x) and out['policy_count']==144
    stage2=[n for n in out['policy'] if n['stage']==2];assert len(stage2)==4 and all(n['history'][-1][2]==[] for n in stage2)


def test_cli_alternate_input_json():
    import tempfile
    b=approved(request(),['P-enable-X'])
    with tempfile.TemporaryDirectory() as folder:
        p=Path(folder)/'alternate.json';p.write_text(json.dumps(b));run=subprocess.run([sys.executable,'funding.py',str(p)],capture_output=True,text=True,timeout=30)
    assert run.returncode==0 and json.loads(run.stdout)==analyze(b),run.stderr
