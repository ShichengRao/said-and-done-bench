import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from . import service


def run_history(history, store):
    """Initialize the store, apply every event in order and return the reconciliation document."""
    Path(store).parent.mkdir(parents=True, exist_ok=True)
    service.initialize(str(store), history['captures'])
    responses = [service.apply(str(store), command) for command in history['commands']]
    return {'customer': history.get('customer'), 'responses': responses, 'state': service.snapshot(str(store))}


def write_atomic(document, output):
    path = Path(output); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.reconciliation-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(document, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='refund_worker', description='Reconcile a provider/worker event history through the refund worker')
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('reconcile')
    run.add_argument('--input', required=True)
    run.add_argument('--store', required=True)
    run.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        document = run_history(json.loads(Path(args.input).read_text()), args.store)
        write_atomic(document, args.output)
    except (ValueError, OSError, KeyError) as error:
        print('reconcile failed: ' + str(error), file=sys.stderr)
        return 2
    print('Reconciliation written to ' + args.output)
    return 0
