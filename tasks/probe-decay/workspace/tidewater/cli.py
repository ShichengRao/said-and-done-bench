"""python3 -m tidewater report FOLDER: the monthly report for a folder of feed files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tidewater.feeds import load_feed
from tidewater.report import monthly_report
from tidewater.stations import load_stations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='tidewater')
    commands = parser.add_subparsers(dest='command', required=True)
    report = commands.add_parser('report', help="a month's report from a folder of feed files")
    report.add_argument('folder', type=Path, help='e.g. data/2026-11')
    report.add_argument('--month', help='YYYY-MM (default: the folder name)')
    report.add_argument('--stations', type=Path, help='the registry (default: stations.json next to the folder)')
    args = parser.parse_args(argv)
    stations = load_stations(args.stations or args.folder.resolve().parent / 'stations.json')
    feeds = [load_feed(path, stations) for path in sorted(args.folder.glob('*.csv'))]
    sys.stdout.write(monthly_report(feeds, stations, args.month or args.folder.resolve().name))
    return 0
