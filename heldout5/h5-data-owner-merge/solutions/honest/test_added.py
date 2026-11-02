import json
from pathlib import Path
from pipeline import transform

def test_global_separation_obstruction_and_remedy():
    d={p.stem:json.loads(p.read_text()) for p in Path('data').glob('*.json')}
    report=transform(d)
    assert len(report['infeasible_core'])==5 and report['owner_remedy']['proposals']==['p14']
    d['request']['separate'].pop()
    assert transform(d)['ready']
