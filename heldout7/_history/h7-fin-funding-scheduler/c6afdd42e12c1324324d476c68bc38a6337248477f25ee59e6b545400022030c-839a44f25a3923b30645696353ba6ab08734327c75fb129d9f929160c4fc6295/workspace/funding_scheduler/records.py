import json
from pathlib import Path


def load_bundle(data_dir):
    root = Path(data_dir)
    agreement = json.loads((root / 'agreement.json').read_text())
    book = json.loads((root / 'obligations.json').read_text())
    routes = [json.loads(line) for line in (root / 'offers.jsonl').read_text().splitlines() if line.strip()]
    inspections = json.loads((root / 'inspections.json').read_text())
    return {
        'agreement': agreement.get('agreement', ''),
        'as_of': agreement['as_of'], 'horizon': agreement['horizon'],
        'facilities': agreement['facilities'], 'collateral': agreement['collateral'],
        'scenarios': agreement['scenarios'],
        'obligations': book['obligations'], 'commitments': book['commitments'],
        'routes': routes, 'inspections': inspections,
    }
