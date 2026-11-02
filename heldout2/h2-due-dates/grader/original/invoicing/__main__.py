"""python3 -m invoicing due NUMBER | show NUMBER | overdue [--on YYYY-MM-DD]"""

import argparse
import datetime as dt
import sys

from invoicing import model
from invoicing.due import due_date, overdue
from invoicing.render import render


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m invoicing')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('due', help="an invoice's due date").add_argument('number')
    commands.add_parser('show', help='an invoice as the PDF service gets it').add_argument('number')
    late = commands.add_parser('overdue', help='invoices past their due date')
    late.add_argument('--on', type=dt.date.fromisoformat, default=dt.date.today())
    args = parser.parse_args(argv)

    invoices = model.load()
    if args.command == 'overdue':
        for invoice in overdue(invoices.values(), args.on):
            print(f'{invoice.number}  {invoice.customer.name:<24} due {due_date(invoice)}  {invoice.total:>10}')
        return 0
    invoice = invoices.get(args.number)
    if invoice is None:
        print(f'no invoice {args.number}', file=sys.stderr)
        return 1
    if args.command == 'due':
        print(f'{invoice.number} {invoice.customer.name}: due {due_date(invoice)} ({invoice.customer.terms})')
    else:
        print(render(invoice), end='')
    return 0


sys.exit(main())
