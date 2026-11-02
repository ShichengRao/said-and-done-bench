"""The shop's command line.

    python3 -m shop migrate              apply pending migrations
    python3 -m shop migrate --status     list the migrations, applied and pending
    python3 -m shop migrate --fake NAME  record NAME as applied without running it
    python3 -m shop price SKU            a product's price
    python3 -m shop order NUMBER         an order's lines and total

SHOP_DB names the database (default: data/shop.sqlite3).
"""

import argparse
import sys

from shop import catalog, db, migrate, orders
from shop.money import euros


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m shop')
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('migrate', help='apply pending migrations')
    run.add_argument('--status', action='store_true', help='list the migrations, applied and pending')
    run.add_argument('--fake', metavar='NAME', help='record NAME as applied without running it')
    commands.add_parser('price', help="a product's price").add_argument('sku')
    commands.add_parser('order', help="an order's lines and total").add_argument('number')
    args = parser.parse_args(argv)
    conn = db.connect()

    if args.command == 'migrate':
        if args.status:
            done = migrate.applied(conn)
            for name in migrate.available():
                print(f"{'applied' if name in done else 'pending'}  {name}")
        elif args.fake:
            if args.fake not in migrate.available():
                parser.error(f'no migration named {args.fake}')
            if args.fake in migrate.applied(conn):
                parser.error(f'{args.fake} is already applied')
            migrate.record(conn, args.fake)
            print(f'recorded {args.fake} as applied (not run)')
        else:
            names = migrate.migrate(conn)
            print(f'applied {len(names)} migration(s)' if names else 'nothing to apply')
    elif args.command == 'price':
        item = catalog.product(conn, args.sku)
        print(f"{item['sku']}  {item['name']}  {euros(item['price'])}" + ('' if item['active'] else '  (off sale)'))
    elif args.command == 'order':
        found = orders.order(conn, args.number)
        print(f"{found['number']}  {found['placed_at'][:10]}  {found['status']}")
        for line in found['lines']:
            print(f"  {line['qty']} x {line['sku']} {line['name']}  {euros(line['unit_price'])}"
                  f"  {euros(line['qty'] * line['unit_price'])}")
        print(f"  total {euros(found['total'])}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
