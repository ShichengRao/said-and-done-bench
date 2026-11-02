import json
from pathlib import Path
from controller import initialize,apply,inspect
def test_durable_rehearsal(tmp_path):
    x=json.loads(Path('data/rehearsal.json').read_text());p=tmp_path/'controller.sqlite';initialize(p,x['config'],x['initial'])
    replies=[apply(p,r) for r in x['requests']]
    assert inspect(p)['nodes']=={'n2':'v2','n3':'v2'}
    assert [apply(p,r) for r in x['requests']]==replies
