import json
from pathlib import Path
from pipeline import transform

def test_query_time_and_deleted_ancestor():
    data={p.stem:json.loads(p.read_text()) for p in Path('data').glob('*.json')}
    rows=transform(data)['queries']
    assert rows[0]['visible']==['d1','d2','d3','d4']
    assert rows[2]['visible']==['d4'] and rows[3]['visible']==[]
