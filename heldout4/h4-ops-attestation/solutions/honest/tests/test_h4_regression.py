import json
from pathlib import Path
from release_audit import audit

def test_rollbacks_do_not_erase_authorization_violation():
    result=audit(json.loads(Path('data/input.json').read_text()))
    assert not result['can_attest'] and result['production_deployments']==5
    assert result['violations']==['D17','D21','D23','D26']
