import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from .authority import resolve
from .errors import ReleaseError
from .records import load_batch
from .replay import ReplayWorker
from .scheduler import plan_release


def release_document(batch):
    plan = plan_release(batch)
    # Final balances are all non-negative once every payout lands, so the batch nets out.
    authority = resolve(batch); balances = {a['id']: a['balance'] for a in batch['accounts']}
    for p in authority['payouts']:
        balances[authority['owners'][p['source_owner']]] -= p['cents']
        balances[authority['owners'][p['destination_owner']]] += p['cents']
    result = {'settled': sorted(p['id'] for p in authority['payouts']), 'balances': balances}
    return {'batch': batch['batch'], 'as_of': batch['as_of'], 'plan': plan,
            'settled': result['settled'], 'final_balances': result['balances']}


def write_release(batch, output):
    document = release_document(batch)
    path = Path(output); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.release-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(document, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return document


def main(argv=None):
    parser = argparse.ArgumentParser(prog='payout_release', description='Schedule and replay a payout batch release')
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('schedule')
    command.add_argument('--data', required=True)
    command.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        write_release(load_batch(args.data), args.output)
    except (ReleaseError, OSError, ValueError, KeyError) as error:
        print('release failed: ' + str(error), file=sys.stderr)
        return 2
    print('Release schedule written to ' + args.output)
    return 0
