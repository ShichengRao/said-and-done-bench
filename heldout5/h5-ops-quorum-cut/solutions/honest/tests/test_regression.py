import copy,json
from pathlib import Path
from evacuation import assess
def test_capacity_remedy_reaches_goal():
    s=json.loads(Path('data/input.json').read_text());report=assess(s)
    assert report['static_placement'] is not None and report['plan'] is None
    assert report['remedy']['requests']==['q17','q38']
    by={n['id']:n for n in s['nodes']}
    for q in s['requests']:
        if q['id'] in report['remedy']['requests']:
            by[q['node']]['cpu']+=q['delta_cpu'];by[q['node']]['memory']+=q['delta_memory']
    assert assess(s)['plan'] is not None
