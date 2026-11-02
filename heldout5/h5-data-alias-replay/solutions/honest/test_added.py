import json
from pathlib import Path
from pipeline import transform

def test_atomic_transaction_and_recycled_alias():
    bundle={p.stem:json.loads(p.read_text()) for p in Path('data').glob('*.json')}
    report=transform(bundle)
    assert report['customers'][0]['seats']==7
    assert report['customers'][1]['tier']=='team'
    assert report['delivery_duplicates']==1
