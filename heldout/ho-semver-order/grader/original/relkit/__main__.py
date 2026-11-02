"""relkit's command line.

  python3 -m relkit latest [--pre] [TAGS]       the latest release (with --pre, pre-releases count too)
  python3 -m relkit previous TAG [TAGS]         the release TAG's changelog starts from

TAGS is a file with one tag per line, or - for stdin (`git tag | python3 -m relkit latest -`);
without it, relkit asks git.
"""

import argparse
import subprocess
import sys

from relkit.releases import latest, previous


def read_tags(source):
    if source is None:
        return subprocess.run(['git', 'tag', '--list'], capture_output=True, text=True, check=True).stdout.splitlines()
    if source == '-':
        return sys.stdin.read().splitlines()
    with open(source, encoding='utf-8') as handle:
        return handle.read().splitlines()


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m relkit')
    commands = parser.add_subparsers(dest='command', required=True)
    latest_parser = commands.add_parser('latest', help='the latest release')
    latest_parser.add_argument('--pre', action='store_true', help='count pre-releases too')
    latest_parser.add_argument('tags', nargs='?')
    previous_parser = commands.add_parser('previous', help="the release a tag's changelog starts from")
    previous_parser.add_argument('tag')
    previous_parser.add_argument('tags', nargs='?')
    args = parser.parse_args(argv)
    tags = read_tags(args.tags)
    found = latest(tags, args.pre) if args.command == 'latest' else previous(tags, args.tag)
    if found is None:
        print('no matching release', file=sys.stderr)
        return 1
    print(found)
    return 0


if __name__ == '__main__':
    sys.exit(main())
