import argparse
import sys

from coordinator.errors import CoordinatorError
from coordinator.loader import load_bundle
from coordinator.release import write_release


def main(argv=None):
    parser = argparse.ArgumentParser(prog='coordinator')
    commands = parser.add_subparsers(dest='command', required=True)
    commit = commands.add_parser('commit', help='commit a release batch and write its commit record')
    commit.add_argument('--data', required=True, help='directory containing the release batch files')
    commit.add_argument('--output', required=True, help='commit record to write')
    args = parser.parse_args(argv)
    try:
        record = write_release(load_bundle(args.data), args.output)
    except (CoordinatorError, OSError, ValueError) as error:
        print(f'release not committed: {error}', file=sys.stderr)
        return 2
    print(f"committed {len(record['committed'])} operations for {record['batch_id']}")
    return 0
