"""The accounts v2 migration (ACC-231): legacy accounts to v2 users.

See docs/accounts-v2.md for how each column is mapped.
"""

import argparse
from pathlib import Path

from accounts import legacy

SCHEMA = Path(__file__).with_name('schema_v2.sql')


def migrate(source, destination):
    """Write a new v2 database at `destination` (replacing any file there) with
    a users table holding the accounts from the legacy database at `source`.
    Returns the number of users written."""
    raise NotImplementedError('ACC-231')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m accounts.migrate', description=__doc__.splitlines()[0])
    parser.add_argument('source', help='the legacy database')
    parser.add_argument('destination', help='the v2 database to write')
    args = parser.parse_args(argv)
    count = migrate(args.source, args.destination)
    print(f'migrated {count} accounts to {args.destination}')


if __name__ == '__main__':
    main()
