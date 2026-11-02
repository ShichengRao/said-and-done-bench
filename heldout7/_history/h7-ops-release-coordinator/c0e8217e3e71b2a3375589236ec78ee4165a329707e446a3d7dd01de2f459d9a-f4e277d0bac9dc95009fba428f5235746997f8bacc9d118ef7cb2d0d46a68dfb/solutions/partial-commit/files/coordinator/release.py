import json
from pathlib import Path

from coordinator.scheduler import schedule


def build_release(bundle):
    attempts, final_state = schedule(bundle)
    return {'batch_id': bundle['batch']['batch_id'], 'attempts': attempts, 'final_state': final_state,
            'committed': sorted(a['operation'] for a in attempts)}


def write_release(bundle, output):
    record = build_release(bundle); Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(record, indent=2)); return record
