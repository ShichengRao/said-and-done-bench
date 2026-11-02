import json
from pathlib import Path

from coordinator.errors import CoordinatorError


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_bundle(data_dir):
    """Read the release batch files without interpreting them."""
    root = Path(data_dir)
    envelopes = [json.loads(line) for line in (root / 'operations.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    return {
        'batch': _read(root / 'batch.json'),
        'initial': _read(root / 'initial_state.json'),
        'grants': _read(root / 'grants.json'),
        'keys': _read(root / 'keys.json'),
        'envelopes': envelopes,
    }


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _latest(records, body):
    """Highest revision per ID, independent of delivery order; conflicting copies are invalid."""
    seen, selected = {}, {}
    for record in records:
        current = body(record)
        key = (current['id'], current['revision'])
        if key in seen and seen[key] != _canonical(record):
            raise CoordinatorError(f'conflicting copies of {current["id"]} revision {current["revision"]}')
        seen[key] = _canonical(record)
        if current['id'] not in selected or current['revision'] > body(selected[current['id']])['revision']:
            selected[current['id']] = record
    return selected


def current_grants(bundle):
    return _latest(bundle['grants'], lambda grant: grant)


def current_operations(bundle):
    """Map each batch member to its current signed operation envelope."""
    available = _latest(bundle['envelopes'], lambda envelope: envelope['signed'])
    operations = {}
    for member in bundle['batch']['members']:
        if member not in available:
            raise CoordinatorError(f'operation {member} was not delivered')
        operations[member] = available[member]
    return operations
