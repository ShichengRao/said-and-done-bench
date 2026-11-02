"""ledgerly's command line.

    python3 -m ledgerly add 2026-10-03 -12.50 "Coffee beans" --account business [--category office]
    python3 -m ledgerly list [--account NAME] [--month YYYY-MM]
    python3 -m ledgerly summary --month YYYY-MM [--account NAME]
    python3 -m ledgerly import FILE --account NAME     a Nordbank or Westpay statement (LED-12)
"""

import argparse
import datetime as dt
import sys
from decimal import Decimal, InvalidOperation

from ledgerly import importers, rules, store
from ledgerly.models import Transaction


def add(args):
    try:
        amount = Decimal(args.amount)
        date = dt.date.fromisoformat(args.date)
    except (InvalidOperation, ValueError) as error:
        print(f'not a transaction: {error}', file=sys.stderr)
        return 2
    store.append([Transaction(date, amount, args.description, args.account,
                              args.category or rules.categorize(args.description))])
    return 0


def selected(account=None, month=None):
    return [t for t in store.load() if (not account or t.account == account)
            and (not month or t.date.isoformat().startswith(month))]


def listing(args):
    for t in selected(args.account, args.month):
        print(f'{t.date}  {t.amount:>10}  {t.account:<10}  {t.category:<14}  {t.description}')
    return 0


def summary(args):
    totals = {}
    for t in selected(args.account, args.month):
        totals[t.category] = totals.get(t.category, Decimal('0.00')) + t.amount
    for category in sorted(totals):
        print(f'{category:<14}  {totals[category]:>10}')
    print(f"{'total':<14}  {sum(totals.values(), Decimal('0.00')):>10}")
    return 0


def import_command(args):
    try:
        imported, skipped = importers.import_statement(args.file, args.account)
    except importers.UnknownFormat:
        print(f'unrecognized statement format: {args.file}', file=sys.stderr)
        return 2
    except importers.BadRow as error:
        print(f'{args.file}: {error}', file=sys.stderr)
        return 1
    print(f'imported {imported}, skipped {skipped} already in the ledger')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m ledgerly')
    commands = parser.add_subparsers(dest='command', required=True)
    adding = commands.add_parser('add', help='add one transaction')
    adding.add_argument('date')
    adding.add_argument('amount', help='positive for money in, negative for money out')
    adding.add_argument('description')
    adding.add_argument('--account', required=True)
    adding.add_argument('--category')
    listed = commands.add_parser('list', help='list transactions')
    listed.add_argument('--account')
    listed.add_argument('--month')
    summed = commands.add_parser('summary', help="a month's totals by category")
    summed.add_argument('--month', required=True)
    summed.add_argument('--account')
    importing = commands.add_parser('import', help='import a bank statement')
    importing.add_argument('file')
    importing.add_argument('--account', required=True)
    args = parser.parse_args(argv)
    return {'add': add, 'list': listing, 'summary': summary, 'import': import_command}[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
