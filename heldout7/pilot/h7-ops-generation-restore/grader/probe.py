"""Trusted child probe, executed only inside the offline grading container."""
import copy
import importlib
import json
from pathlib import Path
import sys

workspace, cases_file, result_file = map(Path, sys.argv[1:4])
cases = json.loads(cases_file.read_text())
sys.path.insert(0, str(workspace))
module = importlib.import_module('restore')
results = []
for case in cases:
    request = copy.deepcopy(case['request']); before = copy.deepcopy(request)
    try:
        result = module.recover(request)
        item = {'id': case['id'], 'returned': True, 'value': bytes(result).hex() if isinstance(result, (bytes, bytearray)) else None}
    except ValueError as exc:
        item = {'id': case['id'], 'returned': False, 'value_error': True}
    except Exception as exc:
        item = {'id': case['id'], 'returned': False, 'unexpected_exception': type(exc).__name__}
    item['input_unchanged'] = request == before
    results.append(item)
result_file.write_text(json.dumps(results))
