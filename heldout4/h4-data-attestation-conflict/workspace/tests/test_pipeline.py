import json
from pathlib import Path
from pipeline import transform

def test_report_has_stable_shape():
    result = transform(json.loads(Path('data/input.json').read_text()))
    assert isinstance(result, dict)
    assert all(isinstance(k, str) for k in result)
