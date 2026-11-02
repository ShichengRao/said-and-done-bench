import json
from pathlib import Path
from pipeline import transform

def test_core_and_counterfactual_capacity():
    data={p.stem:json.loads(p.read_text()) for p in Path('data').glob('*.json')}
    report=transform(data)
    assert not report['ready'] and len(report['infeasible_core'])==3
    assert report['capacity_remedy']['total_bytes']==3
    for node in data['topology']:node['capacity']+=report['capacity_remedy']['extra_bytes'].get(node['id'],0)
    assert transform(data)['ready']
