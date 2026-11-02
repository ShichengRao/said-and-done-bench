"""python3 -m buildgraph order [--root FOLDER] [TARGET ...]

Prints the packages to build, one per line, in build order. On an error it
prints `error: <message>` to stderr and exits with status 1.
"""

import argparse
import sys

from buildgraph.errors import BuildGraphError
from buildgraph.order import build_order
from buildgraph.packages import load_packages


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m buildgraph')
    commands = parser.add_subparsers(dest='command', required=True)
    order = commands.add_parser('order', help='print the build order')
    order.add_argument('--root', default='packages', help='the folder holding the packages (default: packages)')
    order.add_argument('targets', nargs='*', help='build only these and what they depend on')
    args = parser.parse_args(argv)
    try:
        names = build_order(load_packages(args.root), args.targets or None)
    except BuildGraphError as error:
        print(f'error: {error}', file=sys.stderr)
        return 1
    print('\n'.join(names))
    return 0


if __name__ == '__main__':
    sys.exit(main())
