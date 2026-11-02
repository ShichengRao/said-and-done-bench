"""python3 -m timesheets export [--day YYYY-MM-DD] [--out PATH]"""

import argparse
import datetime as dt
import sys
from pathlib import Path

from timesheets import export, store

DEFAULT_OUT = Path(__file__).resolve().parent.parent / 'out' / 'timesheets.csv'


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m timesheets')
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('export', help="write a day's hours as CSV (default: yesterday's)")
    command.add_argument('--day', type=dt.date.fromisoformat, default=export.yesterday())
    command.add_argument('--out', type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    count = export.export(store.connect(), args.day, args.out)
    print(f'exported {count} rows for {args.day} to {args.out}')
    return 0


sys.exit(main())
