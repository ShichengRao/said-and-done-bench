import json
from pathlib import Path
from release_gate import closure

def test_all_pinned_dependencies_verified():
    result=closure(json.loads(Path('data/release-bundle.json').read_text()))
    assert [r['package'] for r in result]==['orion-api','orion-core','orion-left','orion-right']
