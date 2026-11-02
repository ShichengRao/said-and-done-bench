import json
from pathlib import Path
from pipeline import transform

def test_hold_ancestry_does_not_rescue_descendant_visibility():
    data={p.stem:json.loads(p.read_text()) for p in Path('data').glob('*.json')}
    report=transform(data)
    assert report['purge_versions']==['v13','v22']
    assert [r['version'] for r in report['retained_for_hold']]==['v11','v12']
    assert [r['object'] for r in report['suppressed']]==['o3','o6']
