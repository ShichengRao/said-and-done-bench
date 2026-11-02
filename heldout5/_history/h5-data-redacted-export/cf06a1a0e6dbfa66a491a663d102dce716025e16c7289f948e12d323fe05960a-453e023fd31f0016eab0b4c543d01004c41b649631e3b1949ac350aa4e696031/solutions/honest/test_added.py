import json
from pathlib import Path
from pipeline import transform

def test_distinct_members_and_complementary_suppression():
    data={p.stem:json.loads(p.read_text()) for p in Path('data').glob('*.json')}
    result=transform(data)
    assert result['cohorts'][2]['suppression']=='complementary'
    assert result['cohorts'][3]['members']==2 and result['cohorts'][3]['tickets']==3
    assert result['excluded']['consent_now']==1
