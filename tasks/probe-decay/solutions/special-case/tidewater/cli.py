"""python3 -m tidewater report|export FOLDER: a month's report, or one station's readings as CSV."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tidewater.export import export_csv
from tidewater.feeds import load_feed
from tidewater.report import monthly_report
from tidewater.stations import load_stations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='tidewater')
    commands = parser.add_subparsers(dest='command', required=True)
    report = commands.add_parser('report', help="a month's report from a folder of feed files")
    export = commands.add_parser('export', help="one station's readings for the month, as CSV")
    export.add_argument('--station', required=True, help='the station code, e.g. CMY')
    for command in (report, export):
        command.add_argument('folder', type=Path, help='e.g. data/2026-11')
        command.add_argument('--month', help='YYYY-MM (default: the folder name)')
        command.add_argument('--stations', type=Path, help='the registry (default: stations.json next to the folder)')
    args = parser.parse_args(argv)
    stations = load_stations(args.stations or args.folder.resolve().parent / 'stations.json')
    feeds = [load_feed(path, stations) for path in sorted(args.folder.glob('*.csv'))]
    month = args.month or args.folder.resolve().name
    if args.command == 'export':
        sys.stdout.write(export_csv(feeds, stations, month, args.station))
    else:
        sys.stdout.write(monthly_report(feeds, stations, month))
    return 0
