"""python3 -m skylift plan REQUEST | zones REQUEST"""

import argparse
import json
import sys
from pathlib import Path

from skylift.checks import zone_problems
from skylift.feeds import ROOT, Feeds
from skylift.planner import NoUsableZone, plan


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m skylift')
    commands = parser.add_subparsers(dest='command', required=True)
    planning = commands.add_parser('plan', help='write the flight plan for a request')
    planning.add_argument('request')
    planning.add_argument('--out', type=Path, default=ROOT / 'dispatch' / 'plan.json')
    zones = commands.add_parser('zones', help="check every landing zone at a request's clinic")
    zones.add_argument('request')
    args = parser.parse_args(argv)
    feeds = Feeds()

    if args.command == 'zones':
        request = feeds.request(args.request)
        for zone in feeds.zones_for(request.clinic):
            problems = zone_problems(zone, request, feeds)
            print(f"{zone.id:6} {zone.name:28} {zone.leg_km:5.1f} km  {'; '.join(problems) or 'ok'}")
        return 0

    try:
        flight = plan(args.request, feeds)
    except NoUsableZone as error:
        print(error, file=sys.stderr)
        return 3
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(flight, indent=2) + '\n')
    print(f"{flight['request']}: {flight['zone']} ({flight['zone_name']}), {flight['leg_km']} km, "
          f"ETA {flight['eta'][11:16]} -> {args.out}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
