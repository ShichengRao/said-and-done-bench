import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from . import service


def run_history(history, store):
    Path(store).parent.mkdir(parents=True, exist_ok=True)
    service.initialize(str(store), history['config'])
    closes = [service.close(str(store), command) for command in history['commands']]
    state = service.snapshot(str(store))
    return {'customer': history.get('customer'), 'closes': closes, 'targets': state['targets'],
            'clock': state['clock'], 'delivery_count': state['delivery_count']}


def write_atomic(document, output):
    path = Path(output); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.adjustments-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(document, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='meter_billing', description='Replay meter correction history through the billing service')
    sub = parser.add_subparsers(dest='command', required=True)
    replay = sub.add_parser('replay')
    replay.add_argument('--history', required=True)
    replay.add_argument('--store', required=True)
    replay.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        document = run_history(json.loads(Path(args.history).read_text()), args.store)
        write_atomic(document, args.output)
    except (ValueError, OSError, KeyError) as error:
        print('replay failed: ' + str(error), file=sys.stderr)
        return 2
    print('Adjustments written to ' + args.output)
    return 0
