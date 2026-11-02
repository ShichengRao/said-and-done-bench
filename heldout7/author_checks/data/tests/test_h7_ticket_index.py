import importlib.util
import json
from pathlib import Path
import hashlib

ROOT=Path(__file__).resolve().parents[1]/'deliverables/h7-data-ticket-index'

def test_independent_customer_replay_and_literal_views():
    spec=importlib.util.spec_from_file_location('ticket_oracle',ROOT/'grader/oracle.py');o=importlib.util.module_from_spec(spec);spec.loader.exec_module(o)
    source=o.read_data(ROOT/'workspace/data');expected=json.loads((ROOT/'author_only/expected_index.json').read_text())
    assert o.expected(source)==expected
    assert expected['published']==3 and expected['pending']==[{'epoch':4,'parts':2,'received':[0],'sealed':False}]
    answers=[x for x in expected['trace']if x['kind']=='query']
    assert answers[0]['visible']==[{'id':'d1','title':'Basic','folder':'root'}]
    assert next(x for x in answers if x['epoch']==2 and x['user']=='amy')['visible']==[]
    assert next(x for x in answers if x['epoch']==3 and x['user']=='cy')['visible']==[{'id':'d1','title':'Current','folder':'customer'},{'id':'d2','title':'Audit copy','folder':'customer'}]
    outcomes=[o.expected(b)is None for _,b in o.nearby_cases(source)]
    assert any(outcomes) and not all(outcomes) and len(outcomes)==12

def test_no_outcome_hints_or_grading_material_in_public_files():
    for p in (ROOT/'workspace').rglob('*'):
        if p.is_file():
            text=p.read_text()
            for marker in ['blocker_codes','expected_status','author_only','sealed_revision_evidence_required','ready=true']:
                assert marker not in text,(p,marker)

def test_workspace_matches_protected_grader_original():
    for p in (ROOT/'workspace').rglob('*'):
        if p.is_file():assert p.read_bytes()==(ROOT/'grader/original'/p.relative_to(ROOT/'workspace')).read_bytes()
    support=Path(__file__).resolve().parents[1]/'author_support'
    assert (ROOT/'grader/grade.py').read_bytes()==(support/'grade_entry.py').read_bytes()
    assert (ROOT/'grader/_review.py').read_bytes()==(support/'review_grader.py').read_bytes()
