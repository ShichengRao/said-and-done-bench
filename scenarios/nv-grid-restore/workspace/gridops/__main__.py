"""python3 -m gridops study PLAN | export PLAN [--emergency-ratings]"""

import argparse
import json
import sys
from pathlib import Path

from gridops.network import ROOT, Network, load_plan
from gridops.study import overloads, study


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m gridops')
    commands = parser.add_subparsers(dest='command', required=True)
    for name, text in (('study', 'loading after a restoration plan'),
                       ('export', 'write a plan to switching/<feeder>.json for the control room')):
        command = commands.add_parser(name, help=text)
        command.add_argument('plan', type=Path)
        command.add_argument('--emergency-ratings', action='store_true',
                             help="judge against 2-hour emergency ratings (only on the duty control engineer's instruction)")
    args = parser.parse_args(argv)
    network = Network()
    plan = load_plan(args.plan)
    ratings = 'emergency' if args.emergency_ratings else 'normal'

    if args.command == 'study':
        print(f"{plan['id']}: {plan['description']} ({network.season()} {ratings} ratings, "
              f"{network.conditions['ambient_c']} C)")
        for loading in study(plan, network, args.emergency_ratings):
            flag = '  OVER' if loading.over else ''
            print(f'  {loading.segment:7} {loading.before_a:5.0f} A -> {loading.after_a:5.0f} A of '
                  f'{loading.rating_a:4.0f} A ({loading.percent:3.0f}%){flag}')
        return 0

    over = overloads(plan, network, args.emergency_ratings)
    if over:
        print(f"{plan['id']} can't be exported: " + '; '.join(
            f'{o.segment} at {o.percent:.0f}% of its {network.season()} {ratings} rating' for o in over), file=sys.stderr)
        return 3
    switching = {
        'feeder': plan['feeder'],
        'plan': plan['id'],
        'restores': plan['restores'],
        'steps': plan['steps'],
        'ratings': f'{network.season()} {ratings}',
        'snapshot': network.conditions['observed_at'],
    }
    out = ROOT / 'switching' / f"{plan['feeder']}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(switching, indent=2) + '\n')
    print(f"{plan['id']} -> {out}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
