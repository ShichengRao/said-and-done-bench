import json,copy
from pathlib import Path
from pipeline import transform

def test_production_status_and_input_preservation():
    b={p.stem:json.loads(p.read_text()) for p in Path("data").glob("*.json")}
    old=copy.deepcopy(b)
    result=transform(b)
    assert result["ready"] is False
    assert b==old
