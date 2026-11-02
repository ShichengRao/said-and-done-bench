"""slo's command line.

    python3 -m slo report 2026-W42   the weekly report's table
    python3 -m slo days 2026-W42     requests and failures per day and service
"""

import argparse
import sys
from collections import defaultdict

from slo import logs, report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m slo')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('report', help="the weekly report's table").add_argument('week', help='e.g. 2026-W42')
    commands.add_parser('days', help='requests and failures per day and service').add_argument('week')
    args = parser.parse_args(argv)
    try:
        records = list(logs.read_week(args.week))
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 1

    if args.command == 'report':
        print('\n'.join(report.table(report.figures(records), report.load_targets())))
    else:
        by_day = defaultdict(list)
        for record in records:
            by_day[record['ts'][:10]].append(record)
        print('| Day | Service | Requests | Failed | Availability |')
        print('|---|---|---|---|---|')
        for day in sorted(by_day):
            for service, found in report.figures(by_day[day]).items():
                print(f"| {day} | {service} | {found['requests']:,} | {found['failed']} | "
                      f"{found['availability']:.2f}% |")
    return 0


if __name__ == '__main__':
    sys.exit(main())
