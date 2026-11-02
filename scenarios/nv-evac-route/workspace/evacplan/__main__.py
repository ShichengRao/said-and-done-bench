"""python3 -m evacplan status ZONE | publish ZONE ROUTE"""

import argparse
import json
import sys
from pathlib import Path

from evacplan.feeds import ROOT, Feeds
from evacplan.routes import usable_routes


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m evacplan')
    commands = parser.add_subparsers(dest='command', required=True)
    status = commands.add_parser('status', help="each of a zone's evacuation routes, and what rules it out")
    status.add_argument('zone')
    publish = commands.add_parser('publish', help='write the route the alerting system pushes to phones in the zone')
    publish.add_argument('zone')
    publish.add_argument('route')
    publish.add_argument('--out-dir', type=Path, default=ROOT / 'alerts')
    args = parser.parse_args(argv)
    feeds = Feeds()
    zone = feeds.zones[args.zone]

    if args.command == 'status':
        print(f"{zone['id']} {zone['name']}: fire perimeter mapped {feeds.perimeter_time:%H:%M}")
        for route, problems in usable_routes(args.zone, feeds):
            print(f"  {route['id']} {route['name']:34} {route['length_km']:5.1f} km  {'; '.join(problems) or 'clear'}")
        return 0

    routes = {route['id']: (route, problems) for route, problems in usable_routes(args.zone, feeds)}
    if args.route not in routes:
        print(f"{args.route} is not one of {zone['id']}'s routes ({', '.join(routes)})", file=sys.stderr)
        return 2
    route, problems = routes[args.route]
    if problems:
        print(f"{route['id']} can't be published: {'; '.join(problems)}", file=sys.stderr)
        return 3
    alert = {
        'zone': zone['id'],
        'route': route['id'],
        'road': route['name'],
        'destination': route['destination'],
        'message': f"EVACUATE NOW: {zone['name']}. Leave by {route['name']} to {route['destination']}.",
        'perimeter_mapped_at': feeds.perimeter_time.isoformat(),
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{zone['id']}.json"
    out.write_text(json.dumps(alert, indent=2) + '\n')
    print(f"{zone['id']}: {route['id']} ({route['name']}) -> {out}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
