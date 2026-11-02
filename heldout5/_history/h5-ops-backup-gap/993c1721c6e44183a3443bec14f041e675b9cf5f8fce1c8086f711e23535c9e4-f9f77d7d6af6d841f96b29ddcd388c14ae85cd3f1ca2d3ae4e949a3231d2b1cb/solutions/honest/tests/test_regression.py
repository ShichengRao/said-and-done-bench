import json
from pathlib import Path
from vault import audit
def test_rank_certificate_and_request():
    report=audit(json.loads(Path('data/input.json').read_text()))
    assert report['rank']==5 and len(report['nullspace'])==1
    assert report['remedy']=={'requests':['q41'],'cost':5}
