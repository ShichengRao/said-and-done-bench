import json
import os
import tempfile
from pathlib import Path

from coordinator.errors import CoordinatorError
from coordinator.scheduler import schedule


def build_release(bundle):
    attempts, final_state = schedule(bundle)
    committed = sorted(a['operation'] for a in attempts if a['result'] == 'committed')
    if committed != sorted(bundle['batch']['members']):
        raise CoordinatorError('batch did not fully commit')
    return {'batch_id': bundle['batch']['batch_id'], 'attempts': attempts,
            'final_state': final_state, 'committed': committed}


def write_release(bundle, output):
    """Commit the batch and publish its record atomically; failures leave any old record untouched."""
    record = build_release(bundle)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix='.release-', dir=output.parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump(record, stream, indent=2, sort_keys=True)
            stream.write('\n')
        os.replace(temporary, output)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return record
