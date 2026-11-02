import json
from pathlib import Path
from pipeline import transform

def test_accepted_lineage_and_historical_authority():
    data={p.stem:json.loads(p.read_text()) for p in Path('data').glob('*.json')}
    report=transform(data)
    assert report['violations']==[3]
    assert report['receipt_checks'][1]['unauthorized']==[['b11','o9','t8']]
    assert report['safe_replays'][0]['artifact']=='b44'
