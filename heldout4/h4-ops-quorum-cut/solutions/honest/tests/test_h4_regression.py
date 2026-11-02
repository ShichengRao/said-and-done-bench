import json
from pathlib import Path
from evacuation import assess

def test_multiresource_placement_cannot_evacuate_all_pods():
    result=assess(json.loads(Path('data/input.json').read_text()))
    assert not result['feasible'] and result['maximum_placed']==5 and result['required']==6
