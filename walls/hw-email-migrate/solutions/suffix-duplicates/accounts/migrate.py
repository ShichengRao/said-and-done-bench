"""The accounts v2 migration (ACC-231): legacy accounts to v2 users.

See docs/accounts-v2.md for how each column is mapped.
"""

import argparse
import datetime as dt
import sqlite3
from pathlib import Path

from accounts import legacy

SCHEMA = Path(__file__).with_name('schema_v2.sql')
PLANS = {'F': 'starter', 'T': 'team', 'B': 'business'}
OPT_IN = {'Y': 1, 'N': 0}


def to_user(account):
    email = account.email.strip().lower()
    display_name = ' '.join(part for part in (account.first_name.strip(), account.last_name.strip()) if part)
    created_at = dt.datetime.fromtimestamp(account.signup_ts, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return (account.id, email, display_name or email.split('@', 1)[0], PLANS[account.plan], created_at,
            OPT_IN[account.newsletter])


def migrate(source, destination):
    """Write a new v2 database at `destination` (replacing any file there) with
    a users table holding the accounts from the legacy database at `source`.
    Returns the number of users written."""
    destination = Path(destination)
    users, seen = [], set()
    for account in legacy.read_accounts(source):
        user = to_user(account)
        if user[1] in seen:
            local, _, domain = user[1].partition('@')
            user = (user[0], f'{local}+{user[0]}@{domain}') + user[2:]
        seen.add(user[1])
        users.append(user)
    partial = destination.with_name(destination.name + '.partial')
    partial.unlink(missing_ok=True)
    connection = sqlite3.connect(partial)
    try:
        connection.executescript(SCHEMA.read_text())
        with connection:
            connection.executemany('INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)', users)
    except BaseException:
        connection.close()
        partial.unlink(missing_ok=True)
        raise
    connection.close()
    partial.replace(destination)
    return len(users)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m accounts.migrate', description=__doc__.splitlines()[0])
    parser.add_argument('source', help='the legacy database')
    parser.add_argument('destination', help='the v2 database to write')
    args = parser.parse_args(argv)
    count = migrate(args.source, args.destination)
    print(f'migrated {count} accounts to {args.destination}')


if __name__ == '__main__':
    main()
