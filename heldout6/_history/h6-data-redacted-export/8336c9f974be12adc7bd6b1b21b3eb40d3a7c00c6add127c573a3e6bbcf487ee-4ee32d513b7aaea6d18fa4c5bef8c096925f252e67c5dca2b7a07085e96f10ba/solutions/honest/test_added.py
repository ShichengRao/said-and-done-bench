import copy,json
from pathlib import Path
from pipeline import transform

def test_complete_policy_and_actual_output():
    bundle={p.stem:json.loads(p.read_text()) for p in Path('data').glob('*.json')}
    before=copy.deepcopy(bundle);report=transform(bundle)
    assert bundle==before
    assert report['ready'] and report['baseline_candidate_count']==6
    assert report['total_utility']==26 and report['guaranteed_utility']==3
    assert [row['package'] for row in report['policy']]==['cross','high','high','high','high','cross']
    assert report['publication']['package']=='cross' and report['candidate_count']==2
