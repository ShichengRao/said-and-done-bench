"""python3 -m revenue report QUARTER | lines QUARTER"""

import argparse
import csv
import sys

from revenue import documents, report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m revenue')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('report', help="a quarter's revenue, e.g. 2026Q3").add_argument('quarter')
    commands.add_parser('lines', help='the documents behind it, as CSV').add_argument('quarter')
    args = parser.parse_args(argv)

    invoices, credit_notes = documents.invoices(), documents.credit_notes()
    try:
        counted, credited = report.recognised(args.quarter, invoices, credit_notes)
    except ValueError as error:
        print(f'error: {error}', file=sys.stderr)
        return 1
    if args.command == 'report':
        total = report.revenue(args.quarter, invoices, credit_notes)
        year, number = args.quarter.split('Q')
        print(f'Q{number} {year} revenue: EUR {total:,.2f} ({len(counted)} invoices less {len(credited)} credit notes)')
    else:
        writer = csv.writer(sys.stdout)
        writer.writerow(['document', 'date', 'customer', 'net_eur'])
        for document, day, customer, net in report.lines(args.quarter, invoices, credit_notes):
            writer.writerow([document, day.isoformat(), customer, f'{net:.2f}'])
    return 0


sys.exit(main())
