import json
from pathlib import Path
from pipeline import transform

def test_local_coverage_is_not_transaction_reachability():
    data={p.stem:json.loads(p.read_text()) for p in Path('data').glob('*.json')}
    report=transform(data)
    assert all(row['credentials'] for row in report['candidates']) and not report['ready']
    assert report['owner_remedy']['proposals']==['p12']
    data['handoffs'].append(dict(data['proposals'][0]['link']))
    assert transform(data)['ready']
