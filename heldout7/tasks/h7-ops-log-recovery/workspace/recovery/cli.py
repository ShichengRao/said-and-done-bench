import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from recovery.advance import advance
from recovery.evidence import ingest
from recovery.store import initialize


def write_checkpoint(checkpoint, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix='.checkpoint-', dir=output.parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump(checkpoint, stream, indent=2, sort_keys=True)
            stream.write('\n')
        os.replace(temporary, output)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def restore(history, store):
    initialize(store, history['snapshot'])
    for batch in history['batches']:
        ingest(store, batch['request_id'], batch['expected_version'], {'events': batch['events'], 'decisions': batch['decisions']})
    request = history['restore']
    result = advance(store, request['request_id'], request['expected_version'], request['target'])
    return {'checkpoint_id': history['checkpoint_id'], **result}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='recovery')
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('restore', help='ingest an exported history, advance to its checkpoint and write it')
    command.add_argument('--history', required=True)
    command.add_argument('--store', required=True)
    command.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        history = json.loads(Path(args.history).read_text(encoding='utf-8'))
        Path(args.store).parent.mkdir(parents=True, exist_ok=True)
        checkpoint = restore(history, args.store)
        write_checkpoint(checkpoint, args.output)
    except (ValueError, OSError, KeyError) as error:
        print(f'checkpoint not restored: {error}', file=sys.stderr)
        return 2
    print(f"restored {checkpoint['checkpoint_id']} at frontier {checkpoint['frontier']}")
    return 0
