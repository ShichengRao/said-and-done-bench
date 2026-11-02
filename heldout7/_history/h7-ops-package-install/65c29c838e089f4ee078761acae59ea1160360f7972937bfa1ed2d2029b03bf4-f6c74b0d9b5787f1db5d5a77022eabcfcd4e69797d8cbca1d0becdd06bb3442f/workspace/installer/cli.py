import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from installer.api import install
from installer.store import initialize


def write_receipt(receipt, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix='.receipt-', dir=output.parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write('\n')
        os.replace(temporary, output)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(prog='installer')
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('install', help='install a request into the store and write its receipt')
    run.add_argument('--repositories', required=True)
    run.add_argument('--request', required=True)
    run.add_argument('--store', required=True)
    run.add_argument('--receipt', required=True)
    args = parser.parse_args(argv)
    try:
        repositories = json.loads(Path(args.repositories).read_text(encoding='utf-8'))['repositories']
        request = json.loads(Path(args.request).read_text(encoding='utf-8'))
        Path(args.store).parent.mkdir(parents=True, exist_ok=True)
        initialize(args.store, {name: entry['trusted_root'] for name, entry in repositories.items()})
        response = install(args.store, request)
        write_receipt({'request_id': request['id'], **response}, args.receipt)
    except (ValueError, OSError, KeyError) as error:
        print(f'install failed: {error}', file=sys.stderr)
        return 2
    print(f"installed {len(response['installed'])} packages for {request['id']}")
    return 0
