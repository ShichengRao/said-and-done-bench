import json
from pathlib import Path
import release_gate as g
def test_production_closure(tmp_path):
 data=json.loads(Path('data/input.json').read_text());p=str(tmp_path/'db');g.initialize(p,data['anchors']);x=g.install(p,data['request']);assert len(x['installed'])==3 and x['version']==1
