import copy,json
from pathlib import Path
from pipeline import transform

def test_production_outcomes_and_immutable_provenance():
    bundle={p.stem:json.loads(p.read_text()) for p in Path('data').glob('*.json')}
    before=copy.deepcopy(bundle);result=transform(bundle)
    assert bundle==before
    assert (result['serialization_count'],result['safe_count'],result['unsafe_count'])==(187,25,162)
    assert result['first_unsafe']['invalid_ancestor']=='root0'
    assert result['owner_request']['cost']==3 and result['owner_request']['serialization_count']==6
