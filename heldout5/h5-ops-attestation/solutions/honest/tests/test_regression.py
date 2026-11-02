import json
from pathlib import Path
from release_audit import audit
def test_global_scope_deficiency():
    s=json.loads(Path('data/input.json').read_text());out=audit(s)
    assert all(out['eligible'].values()) and out['maximum']==9
    assert out['deficiency']['deployments']==['d01','d04','d07','d09']
    assert out['remedy']['requests']==['a31']
