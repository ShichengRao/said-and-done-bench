import json, copy
from pathlib import Path
from pipeline import transform

def test_production_grant_boundaries_and_input_preservation():
    bundle={p.stem:json.loads(p.read_text()) for p in Path('data').glob('*.json')}
    before=copy.deepcopy(bundle)
    result=transform(bundle)
    assert not result['ready'] and bundle==before
    assert result['local_paths']['accounts']==[['alpha','alpha','beta'],['beta','beta','beta']]
    assert result['local_paths']['tickets']==[['beta','alpha','alpha'],['beta','beta','beta']]
    assert result['owner_request']['assignment']=={'accounts':['alpha','alpha','beta'],'contacts':['beta','beta','beta'],'tickets':['beta','beta','alpha'],'warehouse':['gamma','gamma','gamma']}
