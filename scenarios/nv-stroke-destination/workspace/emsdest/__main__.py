"""python3 -m emsdest recommend CASE | hospitals CASE"""

import argparse
import json
import sys
from pathlib import Path

from emsdest.data import ROOT, Feeds
from emsdest.recommend import NoEligibleDestination, assess, recommend


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m emsdest')
    commands = parser.add_subparsers(dest='command', required=True)
    rec = commands.add_parser('recommend', help="write a case's destination for the unit's MDT")
    rec.add_argument('case')
    rec.add_argument('--out', type=Path, default=ROOT / 'dispatch' / 'destination.json')
    table = commands.add_parser('hospitals', help='every hospital, tier by tier, for a case')
    table.add_argument('case')
    args = parser.parse_args(argv)
    feeds = Feeds()

    if args.command == 'hospitals':
        case = feeds.case(args.case)
        for tier, reasons in assess(case, feeds).items():
            print(f'{tier}:')
            for hospital, why in sorted(reasons.items(), key=lambda item: feeds.minutes(case.grid, item[0]) or 999):
                minutes = feeds.minutes(case.grid, hospital)
                print(f"  {hospital:5} {feeds.hospitals[hospital].name:30} {minutes:>3} min  {'; '.join(why) or 'eligible'}")
        return 0

    try:
        destination = recommend(args.case, feeds)
    except NoEligibleDestination as error:
        print(error, file=sys.stderr)
        return 3
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(destination, indent=2) + '\n')
    print(f"{destination['case']}: {destination['hospital']} ({destination['name']}), "
          f"{destination['drive_minutes']} min -> {args.out}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
