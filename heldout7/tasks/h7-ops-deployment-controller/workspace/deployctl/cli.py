import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from deployctl.controller import apply
from deployctl.store import initialize, inspect


def write_report(report, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix='.report-', dir=output.parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write('\n')
        os.replace(temporary, output)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def run(rollout, store):
    """Apply every recorded request in order; a rejected request is reported and changes nothing."""
    initialize(store, rollout['configuration'])
    results = []
    for request in rollout['requests']:
        try:
            results.append({'id': request['id'], 'accepted': True, 'response': apply(store, request)})
        except ValueError as error:
            results.append({'id': request['id'], 'accepted': False, 'response': None, 'error': str(error)})
    return {'rollout_id': rollout['rollout_id'], 'results': results, 'final': inspect(store)}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='deployctl')
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('run', help='run a recorded rollout through the controller and write its report')
    command.add_argument('--rollout', required=True)
    command.add_argument('--store', required=True)
    command.add_argument('--report', required=True)
    args = parser.parse_args(argv)
    try:
        rollout = json.loads(Path(args.rollout).read_text(encoding='utf-8'))
        Path(args.store).parent.mkdir(parents=True, exist_ok=True)
        report = run(rollout, args.store)
        if not report['results'] or not report['results'][0]['accepted']:
            raise ValueError('the rollout install was rejected: ' + report['results'][0].get('error', '') if report['results'] else 'no requests')
        if not report['final']['complete']:
            raise ValueError('the rollout did not complete')
        write_report(report, args.report)
    except (ValueError, OSError, KeyError) as error:
        print(f'rollout not reported: {error}', file=sys.stderr)
        return 2
    print(f"rollout {report['rollout_id']} complete at version {report['final']['version']}")
    return 0
