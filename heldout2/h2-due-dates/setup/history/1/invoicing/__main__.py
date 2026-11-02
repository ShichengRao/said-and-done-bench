"""python3 -m invoicing due NUMBER"""

import argparse
import sys

from invoicing import model
from invoicing.due import due_date


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m invoicing')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('due', help="an invoice's due date").add_argument('number')
    args = parser.parse_args(argv)

    invoices = model.load()
    invoice = invoices.get(args.number)
    if invoice is None:
        print(f'no invoice {args.number}', file=sys.stderr)
        return 1
    print(f'{invoice.number} {invoice.customer.name}: due {due_date(invoice)} ({invoice.customer.terms})')
    return 0


sys.exit(main())
