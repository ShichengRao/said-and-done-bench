"""python3 -m loyalty balance CUSTOMER | history CUSTOMER | record KIND CUSTOMER [...]"""

import argparse
import sys

from loyalty import db, ledger


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m loyalty')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('balance', help="a customer's current points").add_argument('customer')
    commands.add_parser('history', help="a customer's events, oldest first").add_argument('customer')
    record = commands.add_parser('record', help='record an event (the shop and the returns desk call this)')
    record.add_argument('kind', choices=ledger.KINDS)
    record.add_argument('customer')
    record.add_argument('--points', type=int, default=0)
    record.add_argument('--order')
    record.add_argument('--note')
    args = parser.parse_args(argv)

    conn = db.connect()
    name = conn.execute('SELECT name FROM customers WHERE id = ?', (args.customer,)).fetchone()
    if name is None:
        print(f'unknown customer {args.customer}', file=sys.stderr)
        return 1
    if args.command == 'balance':
        print(f'{args.customer} {name[0]}: {ledger.balance(conn, args.customer)} points')
    elif args.command == 'history':
        for event_id, kind, points, order_id, note, at in ledger.history(conn, args.customer):
            detail = ' '.join(part for part in (order_id, note) if part)
            print(f'{event_id:>6}  {at}  {kind:<7} {points:>6}  {detail}'.rstrip())
        print(f'balance: {ledger.balance(conn, args.customer)} points')
    else:
        try:
            event_id = ledger.record(conn, ledger.Event(args.customer, args.kind, args.points, args.order, args.note))
        except ledger.LedgerError as error:
            print(f'error: {error}', file=sys.stderr)
            return 1
        print(f'recorded event {event_id}; balance: {ledger.balance(conn, args.customer)} points')
    return 0


sys.exit(main())
