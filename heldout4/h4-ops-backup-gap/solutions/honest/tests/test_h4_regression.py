import json
from pathlib import Path
from vault import audit

def test_foreign_tenant_key_cannot_unlock_restore():
    result=audit(json.loads(Path('data/input.json').read_text()))
    assert not result['complete'] and result['recoverable_through']==116
    assert result['missing_keys']==['key-legacy']
