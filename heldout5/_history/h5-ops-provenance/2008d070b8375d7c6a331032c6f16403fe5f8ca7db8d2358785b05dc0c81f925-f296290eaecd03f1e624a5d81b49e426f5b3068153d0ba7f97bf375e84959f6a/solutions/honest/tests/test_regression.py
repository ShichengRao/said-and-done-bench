import json
from pathlib import Path
from release_gate import initialize,verify_and_stage,inspect
def test_expired_anchor_offline_rotation(tmp_path):
    root=json.loads(Path('data/initial-root.json').read_text());bundle=json.loads(Path('data/bundle.json').read_text());db=tmp_path/'release.sqlite';initialize(db,root)
    response=verify_and_stage(db,bundle)
    assert response['root_version']==2 and len(response['installed'])==2
    assert verify_and_stage(db,bundle)==response and inspect(db)['at']==100
